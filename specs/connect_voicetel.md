# Connect VoiceTel Module Specification

## Module Info

- **Name:** Oduist Connect VoiceTel
- **Technical:** `connect_voicetel`
- **Version:** 19.0.1.0.0
- **Depends:** `connect`
- **Python deps:** `voiceml` (the VoiceTel VoiceML SDK, PyPI `voiceml`)
- **Application:** False
- **License:** Other proprietary

## Overview

`connect_voicetel` integrates **VoiceTel VoiceML** — VoiceTel's self-hosted,
Twilio-compatible voice and messaging platform (the `callBroadcast` service
on FreeSWITCH behind an OpenSIPS registrar). The REST API
(`/2010-04-01/Accounts/{AccountSid}/…`), the VoiceML call markup and the
webhooks follow the Twilio contract, so the module is a copy of
`connect_twilio` renamed into its own namespace (ADR-066): the shared ledger
models are extended via `_inherit`, and the PBX configuration is owned as
independent `connect.voicetel.*` models.

Everything contributed to the **shared** models carries the `voicetel_`
prefix (fields *and* methods: `on_voicetel_call_status`, `voicetel_render`,
`get_voicetel_client`, `voicetel_receive`, …) so the module co-installs with
`connect_twilio`, which owns the unprefixed names.

Differences from the Twilio module, all decided in ADR-066:

- the REST client is VoiceTel's own `voiceml` SDK (`voiceml.Client` with
  `base_url`), webhooks validate with `voiceml.webhooks.RequestValidator`,
  and VoiceML markup is built by the module's own builder
  (`models/voiceml_response.py`) — the `twilio` package is not a dependency;
- the browser phone is a JsSIP phone (ported from `connect_asterisk`)
  registered over WSS to the tenant SIP domain with the user's SIP
  credential — no Twilio Voice SDK, no access tokens, no `client` callflow;
- the SIP password is stored readable by its owner and delivered only through
  `res.users.get_voicetel_sip_user_config()`;
- recordings are downloaded into `recording_attachment` on the status
  callback;
- callback URLs carry no `#e=<edge>` fragment; regions, edges, API
  Key/Secret, WhatsApp, content templates and S3 external storage are not
  ported.

The exten dst-Reference mechanics, the callflow language list and the
E.164 caller-ID constraint are deliberate copies of the Twilio/FreeSWITCH/
Telnyx counterparts — **no shared mixin**; fixes must be applied to all
copies (ADR-031).

---

## Models (connect_voicetel/models/)

### settings.py — `connect.settings` (inherit)

Fields: `voicetel_account_sid`, `voicetel_api_key` (groups
`base.group_erp_manager`) + `display_voicetel_api_key` (masked mirror,
`VOICETEL_PROTECTED_FIELDS`), `voicetel_api_host` (default
`voiceml.voicetel.com`), `voicetel_sip_suffix` (default `vml.voice.tel`),
`voicetel_stun_server`,
`voicetel_phone_enabled` (global browser-phone switch), `voicetel_balance`,
`voicetel_auto_sync`, `voicetel_verify_requests`,
`voicetel_fetch_call_prices`.

Methods: `_voicetel_api_host()`, `get_media_auth(media_url)` (account
credentials for the configured host only), `get_voicetel_client()` (returns a
`voiceml.Client`),
`voicetel_sync()` (apps → domains → numbers → caller IDs),
`voicetel_get_phone_settings()` (RPC for the phone service: `phone_enabled`,
`user_agent.phone_sip_protocol/phone_stun_server`),
`voicetel_webhook_url(path)` (absolute callback URL, no fragment),
`compute_voicetel_sip_uri(user)`, `voicetel_external_call_route()`,
`originate_call()` (dispatcher override for key `voicetel`: creates the call
to `sip:<username>@<domain>` with inline `Twiml=`), `get_voicetel_balance()`,
`write()` (masking).

The SDK transport is used as-is (requires `voiceml >= 0.9.4` for
`status_callback` on number update and caller-ID validation).

### user.py — `connect.user` (inherit)

Fields: `voicetel_username` (UNIQUE, alphanumeric), `originate_provider` /
`message_provider` `selection_add=[('voicetel', 'VoiceTel')]`,
`voicetel_exten` (M2O `connect.voicetel.exten`), `voicetel_exten_number`
(related, stored, in `_pbx_number_fields()`), `voicetel_outgoing_callerid`,
`voicetel_sid` (credential SID), `voicetel_password` (groups admin + user,
never masked), `voicetel_domain` (M2O domain, cascade), `voicetel_sip_enabled`,
`voicetel_ring_timeout`, `voicetel_phone_enabled`, `voicetel_ring_volume`,
`voicetel_mask_call_number`, `voicetel_call_popup_is_enabled`,
`voicetel_call_popup_is_sticky`, `voicetel_uri` (computed
`username@domain_name`), `voicetel_application`.

Constraints: username/domain required when SIP is enabled; the username
cannot change while the credential exists; enabling SIP registers the `sip`
user callflow, `voicemail_enabled` the `voicemail` one (prio 10).

Credential lifecycle (`voicetel_auto_sync`): `create()` generates a password
when none is given and creates the credential; `write()` creates/updates/
deletes it when `voicetel_sip_enabled`/`voicetel_password` change;
`unlink()` deletes it. Context keys: `no_voicetel_create`,
`skip_voicetel_sync`.

Dialplan: `voicetel_render(request, params)` (stateful callflow walk, same
algorithm as Twilio), `voicetel_render_sip()` (one `<Dial><Sip>` on the
tenant domain), `voicetel_render_voicemail()`,
`voicetel_get_greeting_message()`, `voicetel_get_voicemail_prompt()`,
`voicetel_on_call_action(record_id, request)`,
`_voicetel_get_dial_action_url()`, `_voicetel_is_call_action_final()`,
`_voicetel_get_caller_id()`, `voicetel_caller_id()` (extension → own caller
ID → default → username), `get_user_by_uri()` (matches `sip:user@host`
only when `host` is one of this module's domains; bare usernames too).

### res_users.py — `res.users` (inherit)

`get_voicetel_sip_user_config(user_id)`: for the calling user only, returns
`{'user_config': {sip_user, sip_password, sip_auth_user, phone_sip_proxy,
phone_realm, phone_websocket}, 'phone_config': {phone_ring_volume,
mask_call_number, call_popup_is_enabled, call_popup_is_sticky, record_calls,
exten, outgoing_callerid}}`, or `False` when the browser phone is not
enabled for that user.

### domain.py — `connect.voicetel.domain`

Fields: `sid`, `application` (M2O voiceml, required, default the
**SIP Domain Calls** app), `cred_list_sid`, `subdomain` (DNS label,
UNIQUE), `domain_name` (computed `<label>.<suffix>`), `wss_url` (computed),
`friendly_name`, `sip_registration`, `delete_protection`.

Methods: `create_voicetel_sip_domain(client)` (domain + credential list +
registrations/calls mappings + credentials for the domain's SIP-enabled
users), `_import_existing_domain_by_name()` (adopts a domain the account
already holds; refuses one held by another tenant),
`_import_sip_credentials_from_voicetel()`, `create_domain()`,
`update_voicetel_domain()`, `sync()`, `route_call(request, params)`
(exten → `exten.render()`, `+E164` → `originate_external_call()`),
`originate_external_call()`. A 409 / 21631 "domain taken" answer is handled
like "already exists" and never re-creates.

### voiceml.py — `connect.voicetel.voiceml`

The Application mirror. Fields: `sid`, `name`, `description`, `code_type`
(`voiceml` | `python` | `model_method`), `voiceml`, `python_code`, `model`,
`method`, `voice_url` / `voice_fallback_url` / `voice_status_url`
(computed, `/voicetel/webhook/voiceml/<id>`), `exten`, `exten_number`.
Methods: `create_voicetel_app()`, `update_voicetel_app()` (by SID only;
re-creates on *not found*, never on other failures), `sync()`, `render()`,
`render_voiceml()` (Jinja2), `render_python()` (exec with the `twilio`
helper), `create_extension()`. `pretty_xml()` helper.

### number.py — `connect.voicetel.number`

Fields: `phone_number`, `friendly_name`, `destination` (`user` | `callflow`
| `voiceml`), `callflow`, `user`, `voiceml`, `is_ignored`, `sid`,
computed `voice_url` (`/voicetel/webhook/number`), `voice_fallback_url`,
`voice_status_url`, `message_url` / `message_fallback_url`
(`/voicetel/webhook/message`, always set). Methods: `update_voicetel_number()`
(IncomingPhoneNumbers update), `sync()` (import; removes numbers gone from
the account), `render()`, `route_call()` (by `Called`/`To`).

### exten.py — `connect.voicetel.exten`

Copy of the Twilio extension (dst Reference over `connect.user`,
`connect.voicetel.callflow`, `connect.voicetel.voiceml`; back-link
`voicetel_exten` on the user). `_render_dst()` dispatches a user to
`voicetel_render()`.

### callflow.py — `connect.voicetel.callflow`, `connect.voicetel.callflow_choice`

Copy of the Twilio call flow (Gather DTMF/speech, choices, ring users,
voicemail). Ring users are dialed with one `<Sip>` per user on the tenant
domain. `voicetel_on_call_action(flow_id, request)`, `gather_action()`.

### outgoing_callerid.py — `connect.voicetel.outgoing_callerid`

Copy of the Twilio caller ID: `callerid_type` `outgoing_callerid` (verified
external number) | `number` (owned DID), `is_default`, E.164 constraint,
`validate()` (`validation_requests.create` with the status callback),
`update_status(params)` (`VerificationStatus`, `OutgoingCallerIdSid`),
`sync()`.

### user_callflow.py — `connect.voicetel.user_callflow`, `connect.voicetel.user_callflow_call`

Per-user ordered callflow steps (`callflow_type` `sip` | `voicemail`,
`method` `voicetel_render_sip` | `voicetel_render_voicemail`) and the
per-call walk log.

### message_configuration.py — `connect.voicetel.message_configuration`

Per-number destination model + default values for records created from
inbound messages (admin-only).

### call.py — `connect.call` (inherit)

Fields: `voicetel_call_sid`, `voicetel_price`, `voicetel_price_unit`,
`voicetel_is_price_fetched`. Methods: `on_voicetel_call_status(params)`
(channel adapter → `process_call_event`, error data, incoming-call
notification, price marking), `on_voicetel_vm_recording_status()`,
`on_voicetel_call_action()`, `voicetel_fetch_call_prices_batch()` (cron),
`voicetel_transfer()` (conference-based attended transfer).

### channel.py — `connect.channel` (inherit)

`on_voicetel_call_status()` → `_map_voicetel_params()` →
`process_channel_event()`; `_strip_exten_plus()`; softphone recording
controls `_softphone_recording_{state,start,stop}_voicetel()`
(`/Calls/{Sid}/Recordings` create/update) and `_softphone_forward_voicetel()`
(redirects the other leg to the SIP domain app with `forward_to`);
`voicetel_notify()` (incoming-call bus notification).

### message.py — `connect.message` (inherit)

Field `voicetel_account_sid`. `voicetel_receive(params)` (inbound
`SmsStatus=received` → message + routing + chatter; otherwise status update
from `MessageStatus`/`SmsStatus`), `send()` (dispatcher override for key
`voicetel`, SMS only), `voicetel_client_send()` (Messages create with the
status callback), `action_retry()`, `_compute_direction()` override.

### recording.py — `connect.recording` (inherit)

`on_voicetel_recording_status(params)` (completed only; upserts by SID,
then `voicetel_download()`), `voicetel_download()` (Basic auth, 30 s
timeout, stores `recording_attachment` + `recording_filename`; failures keep
`media_url`), `_voicetel_media_url()`, `prepare_voicetel_data()`.

---

## Controllers (connect_voicetel/controllers/voicetel_webhooks.py)

All routes `type='http'`, `auth='public'`, `csrf=False`, POST, executed as
`connect.user_connect_webhook`, guarded by `check_signature()`
(`RequestValidator(voicetel_api_key)` over the https URL as transmitted +
POST form; toggle `voicetel_verify_requests`):

| Route | Handler |
|---|---|
| `/voicetel/webhook/domain` | `connect.voicetel.domain.route_call` |
| `/voicetel/webhook/callstatus` | `connect.call.on_voicetel_call_status` |
| `/voicetel/webhook/number` | `connect.voicetel.number.route_call` |
| `/voicetel/webhook/outgoing_callerid` | `connect.voicetel.outgoing_callerid.update_status` |
| `/voicetel/webhook/callflow/<id>/gather` | `connect.voicetel.callflow.gather_action` |
| `/voicetel/webhook/vm_recordingstatus` | `connect.call.on_voicetel_vm_recording_status` |
| `/voicetel/webhook/<model>/call_action/<id>` | `voicetel_on_call_action` on `connect.user` or `connect.voicetel.callflow` only |
| `/voicetel/webhook/recordingstatus` | `connect.recording.on_voicetel_recording_status` |
| `/voicetel/webhook/callaction` | `connect.call.on_voicetel_call_action` |
| `/voicetel/webhook/voiceml/<id>` | `connect.voicetel.voiceml.render` |
| `/voicetel/webhook/message` | `connect.message.voicetel_receive` |

---

## Wizard

`sms.composer` (inherit): `outgoing_callerid` selection over
`connect_voicetel_number`; `_action_send_sms()` calls `connect.message.send()`.

---

## Security (security/access_rules.xml)

| Model | Connect User | Connect Admin | Webhook |
|---|---|---|---|
| `connect.voicetel.voiceml`, `.domain`, `.exten`, `.callflow`, `.callflow_choice`, `.number` | read | CRUD | read |
| `connect.voicetel.outgoing_callerid` | read | CRUD | read + write |
| `connect.voicetel.user_callflow`, `.user_callflow_call` | read | CRUD | — |
| `connect.voicetel.message_configuration` | — | CRUD | — |
| `sms.composer` | CRUD | (inherits) | — |

---

## Data

- `data/voiceml.xml` (noupdate): **SIP Domain Calls** (`model_method`
  `connect.voicetel.domain.route_call`), **Reject**, **Connection Failed**.
- `data/ir_cron.xml`: **Fetch Call Prices from VoiceML** (5 min,
  `voicetel_fetch_call_prices_batch`).

---

## Views & Menu

**VoiceTel** submenu (`menu_connect_voicetel`, sequence 50): Numbers,
Extensions, Call Flows, Outgoing Caller IDs, VoiceML Apps, SIP Domains,
Messages (list + admin-only Message Configuration), Configuration ▸ Settings
(standalone `connect_settings_form_voicetel` via `open_settings_form`).
`connect.user` list/form get the `voicetel_*` columns and a **VoiceTel
Phone** page (SIP Account + Browser Phone groups); `connect.call` form a
**VoiceTel** page; `connect.message` form the account SID.

---

## Frontend (static/src/)

JsSIP phone ported from `connect_asterisk`: `js/core.js` registers the
`connect_voicetel_phone` service, which loads the systray + main phone
components when `connect.settings.voicetel_get_phone_settings().phone_enabled`
and `res.users.get_voicetel_sip_user_config(uid)` answer. The UA registers to
`phone_websocket` (`wss://<domain_name>:8443`, the fixed `VOICETEL_WSS_PORT`) with
`sip:<sip_user>@<phone_sip_proxy>` and the SIP password. Transfer and
forward use SIP REFER (no DTMF feature codes). `widgets/phone_field` prefers
the browser phone for click-to-call and falls back to
`connect.settings.originate_call`.

---

## Tests (connect_voicetel/tests/)

`test_callflow`, `test_channel_exten_number`, `test_exten`,
`test_outgoing_callerid`, `test_recording_media` (media auth per host),
`test_recording_download` (attachment on callback, mocked `requests`),
`test_user_caller_id` (caller ID, SIP leg, domain-scoped URI lookup),
`test_user_prompts`, `test_user_sip_account` (credential lifecycle, phone
config channel), `test_voiceml_client` (host rewrite, callback URLs),
`test_webhook_signature` (HttpCase), `test_inbound_message_routing`.

---

## Live verification checklist (not covered by tests)

1. Helper-library requests reach `voicetel_api_host` with Basic auth
   (`calls.create`, `sip.domains`, `incoming_phone_numbers`,
   `outgoing_caller_ids`, `validation_requests`, `applications`, `messages`,
   `balance`).
2. SIP domain creation under the suffix; credential list + both mappings;
   credential creation and WSS registration of the browser phone and the
   VoiceML Phone app with the same credential.
3. Inbound DID → `/voicetel/webhook/number` with a valid signature;
   `CallStatus=ringing` on the pre-answer fetch.
4. **Blocked upstream today: the deployed OpenSIPS edge routes calls placed
   from a registered device straight to the carrier** — the SIP domain's
   voice URL never fires, so `/voicetel/webhook/domain` and browser
   click-to-call routing cannot pass until the OpenSIPS config relays those
   INVITEs into FreeSWITCH (or VoiceTel decides the direct-carrier path is
   final and the Odoo-side feature surface is trimmed). Tracked as the
   remaining platform item.
5. `POST /Calls` with `To=sip:<user>@<domain>` and inline `Twiml` for
   server-side click-to-call; `From` accepted by the caller-ID gate.
6. Recording callback timing: the WAV is still served when the download
   runs; `.wav` content type; 302 to a bucket when configured.
7. SMS send with `StatusCallback`; inbound message with `SmsStatus=received`.
8. Caller-ID verification call and the `VerificationStatus` callback.
9. `X-Twilio-Signature` validation on action URLs carrying a query string.

## Known platform constraints (verified against the VoiceML source)

- Recording callbacks may name the **node's regional host**
  (e.g. `east-1.us.voiceml.voicetel.com`), not `voicetel_api_host`; the media
  auth gate only attaches credentials to the configured host, so confirm the
  fleet's `TLS_DOMAIN` before relying on the callback download.
- VoiceTel-carried SMS reports only `sent`/`failed`; `delivered` never fires
  and `ErrorMessage` is never sent.
- SIP credential creation refuses a duplicate username with HTTP 408 /
  21632 ("already in use"); SIP domain creation refuses a taken name with
  409 / 21631. `friendly_name` on IncomingPhoneNumbers and `domain_name` on
  SIP domain update are accepted-and-dropped server-side.
- The stock TTS engine renders only en-US/es-ES/fr-FR/de-DE; other `<Say>`
  languages fall back to English pronunciation. Speech `<Gather>` needs a
  tenant-configured STT provider beyond English.
- `<Dial>` action callbacks never report `DialCallStatus=canceled` (except
  conference legs); no ErrorCode/ErrorMessage are sent on call status
  callbacks except the SIP-guard failure (32011).
