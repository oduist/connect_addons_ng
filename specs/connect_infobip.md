# connect_infobip — Infobip Integration Module

## Module Info

- **Name**: Oduist Connect Infobip
- **Technical Name**: `connect_infobip`
- **Version**: 19.0.1.0.0
- **Depends**: `connect`
- **Python Dependencies**: none (plain `requests`; the official Infobip
  Python SDK does not cover the Voice/Calls and Numbers APIs — ADR-036)
- **Application**: No
- **License**: Other proprietary

## Overview

Infobip provider module built in the image of connect_twilio/connect_telnyx
(ADR-031/ADR-032/ADR-036). Owns its PBX configuration as
`connect.infobip.*` models and `_inherit`s the shared ledger models with
`infobip_`-prefixed fields/methods, so it co-installs with the other
providers.

**Key difference: no TwiML analog.** Infobip Calls is event-driven —
webhooks deliver events (`CALL_RECEIVED`, `CALL_ESTABLISHED`,
`DIALOG_FAILED`, ...) and the module answers with REST actions
(`/calls/1/calls/{id}/say`, `/calls/1/dialogs`, ...). The render pipeline
of the XML providers is replaced by an event dispatcher plus routing
state on the parent `connect.channel`; ring timers are the platform's
`connectTimeout`, never Odoo-side timers.

**v1 scope**: direct number routing to users (WebRTC web phone and/or
external phone via prioritized steps) or external numbers, click-to-call,
web phone, recordings + core transcription, SMS (send/receive/DLR),
WhatsApp (senders/templates/composer), message routing configuration.
**Excluded** (ADR-036): IVR/callflows, recorded voicemail, RCS, Viber,
number purchasing, call price fetch, transfers, parallel ring.

**Deliberately duplicated blocks** (no mixins — ADR-031): the exten
dst-Reference mechanics and the caller-ID E.164/is_default logic are
full copies; fixes must land in connect_twilio, connect_freeswitch,
connect_telnyx AND connect_infobip in the same commit. The callflow
language list is NOT copied (no IVR in v1).

## Models (`connect_infobip/models/`)

### settings.py — `_inherit connect.settings`

| Field | Description |
|-------|-------------|
| `infobip_base_url` | Personalized API host (`https://{x}.api.infobip.com`) |
| `infobip_api_key` | Secret (groups `base.group_erp_manager`, ADR-025) |
| `display_infobip_api_key` | Masked twin (`INFOBIP_PROTECTED_FIELDS` + `write()` pass) |
| `infobip_webhook_token` | Auto-generated shared webhook secret (ADR-036) |
| `infobip_verify_requests` | Webhook auth toggle (default on, fail-closed) |
| `infobip_auto_sync` | Push per-number config on write/sync |
| `infobip_calls_configuration_id` | Calls application ID (auto-created as "Odoo Connect") |
| `infobip_webrtc_application_id` | Optional WebRTC application for token minting |
| `infobip_webphone_via_rest` | Web phone fallback: dial via REST originate |
| `infobip_webhook_urls` | Computed listing of the webhook URLs (with token) |

Methods: `infobip_api_request()` / `infobip_api_request_raw()` (App-key
HTTP client; errors surface `requestError.serviceException.text`, the key
never leaks), `infobip_list_numbers()` (paginated Numbers API),
`infobip_sync()` (webhooks setup → numbers → caller IDs → non-fatal
WhatsApp senders/templates), `infobip_setup_webhooks()` (best-effort
Calls-configuration auto-create + manual-instructions notification),
`get_infobip_webhook_url(endpoint)`, `originate_call()` override
(dispatcher guard `_get_originate_provider(user) != 'infobip'` →
`super()`; otherwise `POST /calls/1/calls` to the agent's endpoint with
correlation `customData`, eager channel upsert under the per-callId
advisory lock).

### channel.py — `_inherit connect.channel`

Fields: `infobip_leg`, `infobip_dialog_id`, `infobip_route_number`,
`infobip_route_user`, `infobip_route_step`, `infobip_originate_dest`,
`infobip_pending_say`, `infobip_pending_say_language`,
`infobip_hangup_after_say`, `infobip_last_event_ts`.

Methods: `_map_infobip_params(event)` (event → `process_channel_event`
dict; statuses: RECEIVED/RINGING/PRE_ESTABLISHED→ringing,
ESTABLISHED→in-progress, FINISHED→completed, FAILED→by error code:
NO_ANSWER→no-answer, BUSY/REJECTED/DECLINED→busy, CANCELED→canceled,
else failed; duration only on terminal events; WEBRTC endpoints render as
`client:{identity}@infobip`), `on_infobip_event()` (ledger feed with
terminal-status and stale-timestamp guards),
`infobip_answer_say_hangup(text, language='en')` (answer → say →
SAY_FINISHED → hangup chain; the language is persisted in
`infobip_pending_say_language` and sent with the flushed `/say` — the
user voicemail prompt uses `connect.user.infobip_say_language()`,
system apologies stay `'en'`, ADR-037), `_infobip_create_dialog()`
(Dialog bridge with `childCallRequest`, `connectTimeout`, correlation
customData, optional recording, eager child upsert),
`_infobip_start_user_ring()` / `_infobip_ring_step()` /
`_infobip_advance_ring()` / `_infobip_ring_exhausted()` (ring machine
over `connect.infobip.user_callflow` steps; exactly-once advance guarded
by `route_step`/dialog id), `_infobip_bridge_external()`,
`_infobip_on_established()` / `_infobip_bridge_originate_dest()`
(click-to-call second leg), `infobip_close_stale()` (cron safety net:
reconcile hung legs against `GET /calls/1/calls/{id}`).

### call.py — `_inherit connect.call`

Field `infobip_dialog_id`. `on_infobip_voice_event(event, kind)` — the
webhook dispatcher (always ACKs; per-callId
`pg_advisory_xact_lock(hashtext(callId))`): CALL_RECEIVED → PSTN
`number.route_call()` or WEBRTC `_infobip_route_internal()` (web-phone
`callApplication` dial routed by `customData.dialed_number`); status
events → channel adapter + `process_call_event` (benign
NO_ANSWER/BUSY/CANCELED are not errors); DIALOG_* bookkeeping/advance;
SAY_FINISHED → hangup; RECORDING_FINISHED → recording adapter; unknown →
debug log.

### recording.py — `_inherit connect.recording`

Attachment-first (ADR-036): `on_infobip_recording(event)` creates rows
with `infobip_file_id` + `infobip_download_pending` (created with
`skip_transcription`); cron `infobip_fetch_pending()` downloads bytes via
the authorized `GET /calls/1/recordings/files/{id}` into
`recording_attachment`, then sets `transcription_pending`. Retries capped
at `MAX_DOWNLOAD_ATTEMPTS`. Requires the core seam where
`transcribe_recording()` prefers `recording_attachment` (see
specs/connect_core.md).

### message.py — `_inherit connect.message`

`infobip_bulk_id`; `_compute_direction()` override (Infobip numbers +
WhatsApp senders; co-installation last-loaded-wins limitation restated,
ADR-032/ADR-036); `send()` → `infobip_client_send()` =
`POST /sms/2/text/advanced` with per-send DLR `notifyUrl` (MSISDNs sent
without `+`); `infobip_receive()` / `infobip_receive_whatsapp()` (inbound
`{results: [...]}` envelopes) sharing `_infobip_dispatch_inbound()`
(threading on the last exchanged message, `message_configuration`
routing, chatter post — Telnyx-shaped); `infobip_process_delivery_report()`
(unified SMS+WhatsApp DLR: `status.groupName` → status, failed groups set
error fields + WhatsApp chatter note); `action_retry()`.

### user.py — `_inherit connect.user`

`originate_provider` `selection_add=[('infobip','Infobip')]`;
`_pbx_number_fields() + ['infobip_exten_number']`. No per-user SIP at
Infobip: the agent endpoints are `infobip_identity` (WebRTC, unique,
auto-generated from the login when the web phone is enabled) and
`infobip_phone_number` (E.164 external phone, rendered with `widget="phone"`
on the user form). Enable/priority/timeout
fields per endpoint maintain `connect.infobip.user_callflow` rows via
constrains (`_manage_infobip_channel_callflow`). Also: `infobip_exten`
(+related number), `infobip_outgoing_callerid`,
`infobip_whatsapp_sender_id`, `get_user_by_uri()` chained override
matching `client:{identity}@infobip`, `get_user_by_infobip_identity()`,
`get_infobip_client_token()` (`POST /webrtc/1/token`; returns
`{token, identity, calls_config_id, via_rest, expiration}`),
`create_infobip_extension()`, `infobip_render_voicemail_prompt()`
(jinja2, spoken by the say fallback), `infobip_say_language()`
(BCP-47 `connect.user.language` → Infobip say code via
`INFOBIP_SAY_LANGUAGE_MAP`, fallback = base subtag, ADR-037).

### Owned config models

| Model | Purpose |
|-------|---------|
| `connect.infobip.number` | Synced DIDs (`number_key`, `capabilities`); `destination` user/external (+`external_callerid_mode`); pushes SMS forward-to-HTTP and the voice action best-effort; `route_call(event)` routes CALL_RECEIVED |
| `connect.infobip.exten` | dst-Reference mechanics (duplicated block); v1 dst = `connect.user` only; no render pipeline |
| `connect.infobip.outgoing_callerid` | Owned-numbers caller IDs (duplicated E.164/is_default block), synced from the Numbers API |
| `connect.infobip.user_callflow` | Ring steps (`callflow_type` client/phone, `prio`, `ring_timeout`); no per-call progress model — progress lives on the channel |
| `connect.infobip.whatsapp_sender` | Readonly-synced senders (`GET /whatsapp/1/senders`), `send_whatsapp()` text/template, 24h window check, `get_default_sender()`, `chatter_post()` |
| `connect.infobip.whatsapp_template` | Per-sender templates (`sender_id` required): `create_in_infobip()` → `POST /whatsapp/2/senders/{sender}/templates`, `sync()`, `_as_message_content()` |
| `connect.infobip.message_configuration` | Admin-only inbound routing (number → destination model + default values) |

## Controllers (`controllers/`)

`token_auth.py`: `check_infobip_webhook_auth()` — shared-token check
(`?token=` or Basic-Auth password, `secrets.compare_digest`, fail-closed;
toggle `infobip_verify_requests`). Infobip does not sign webhooks.

`infobip_webhooks.py` — all POST, `type='http'`, `auth='public'`,
`csrf=False`, `readonly=False`, executed as `connect.user_connect_webhook`,
always 200 (errors logged):

| Route | Handler |
|-------|---------|
| `/infobip/webhook/voice/received` | `connect.call.on_infobip_voice_event(event, 'received')` |
| `/infobip/webhook/voice/event` | `connect.call.on_infobip_voice_event(event, 'event')` |
| `/infobip/webhook/message` | `connect.message.infobip_receive(event)` |
| `/infobip/webhook/whatsapp` | `connect.message.infobip_receive_whatsapp(event)` |
| `/infobip/webhook/message_status` | `connect.message.infobip_process_delivery_report(event)` |

## Wizards (`wizard/`)

- `sms_composer.py` — `_inherit sms.composer`: `outgoing_callerid`
  selection from `connect_infobip_number`, `_action_send_sms()` →
  `connect.message.send()`.
- `whatsapp_composer.py` — `connect.infobip.whatsapp_composer`
  TransientModel: sender/recipient (`widget="phone"`)/template/variables/preview →
  `whatsapp_sender.send_whatsapp()`.

## Security (`security/access_rules.xml`)

| Model | admin | user | webhook |
|-------|-------|------|---------|
| exten, number, outgoing_callerid, whatsapp_sender | CRUD | R | R |
| user_callflow, whatsapp_template | CRUD | R | — |
| message_configuration | CRUD | — | — |
| whatsapp_composer | CRUD | CRUD | — |
| sms.composer | — | CRUD | — |

## Data (`data/ir_cron.xml`)

- *Fetch Recordings* (1 min) → `connect.recording.infobip_fetch_pending()`
- *Close Stale Channels* (10 min) → `connect.channel.infobip_close_stale()`

## Views & Menu

**Connect → Infobip** (seq 50): Numbers (10), Extensions (20), Outgoing
Caller IDs (40), Messages (70: Messages / Message Configuration /
WhatsApp Senders / WhatsApp Templates), Configuration (100, admin:
Settings via `ir.actions.server` →
`open_settings_form("connect_infobip.connect_settings_form_infobip",
"Infobip Settings")` — standalone primary form, never a notebook page in
the core settings). Core user form/list extended with an "Infobip Phone"
tab; core call form with an "Infobip" page.

## Frontend (`static/src/`)

Port of the connect_telnyx phone widget to the vendored
`lib/infobip.rtc.js` (official infobip-rtc 2.x browser bundle; exports
copied onto `window`, lazy-loaded via `loadJS`, not in the assets
bundle). `js/main.js` boots on `connect.user.get_infobip_client_token`.
`phone.js`: `InfobipSession` adapter (accept/decline/hangup/mute/
sendDTMF; `customParameters` from the call's `customData` —
From/CallerName/Partner/autoAnswer set by the server-side legs); remote
audio from the `established` event stream; component-played ringtone
(the SDK has none); outgoing calls via
`callApplication(callsConfigurationId, {customData: {dialed_number}})`
with a REST-originate fallback (`infobip_webphone_via_rest`); token
refresh by re-init, proactively at ~90% TTL. Other components/services/
widgets are mechanical renames of the Telnyx tree; `phone_field.js`
patches the core PhoneField for click-to-call + WhatsApp composer. The
**Calls history tab** and the **active-calls systray widget** are imported
from / registered by core `connect` rather than copied here
(`@connect/components/calls/calls`, `connect/services/active_calls`).

## Tests

Tests are colocated in `connect_infobip/tests/` (ADR-034: common,
settings, exten, outgoing_callerid, message send/receive, voice events,
ACL). All HTTP is mocked.

## Known limitations

- `connect.message.send()` / `_compute_direction()` / `sms.composer`:
  last-loaded provider wins on co-installation (core dispatcher hook
  still deferred — ADR-032/ADR-036).
- API payload shapes flagged for live confirmation are listed in
  ADR-036 (event envelope, dialog `connectTimeout`, customData
  round-trip, Numbers API config schemas, WhatsApp senders listing,
  DLR vocabulary, Subscriptions API variant).

## Dependencies Summary

```
connect_infobip
└── connect (core ledger, settings dispatcher, webhook user, OpenAI transcription)
Python: requests (stdlib of the Odoo stack), no provider SDK
JS: vendored infobip-rtc 2.x browser bundle
```
