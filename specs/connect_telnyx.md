# Connect Telnyx Module Specification

## Module Info

- **Name:** Oduist Connect Telnyx
- **Technical:** `connect_telnyx`
- **Version:** 19.0.1.4.3
- **Depends:** `connect`
- **Python deps:** `telnyx`, `nacl` (PyNaCl)
- **Application:** False
- **License:** Other proprietary

## Overview

The `connect_telnyx` module extends the core `connect` module with
Telnyx-specific functionality, structurally mirroring `connect_twilio`
(ADR-032). The shared ledger models (`connect.call`, `connect.channel`,
`connect.message`, `connect.recording`, `connect.user`,
`connect.settings`) are extended via `_inherit`; per ADR-031 the module
**owns its PBX configuration models** as independent `connect.telnyx.*`
models: `connect.telnyx.exten`, `connect.telnyx.callflow`
(+`_choice`), `connect.telnyx.number`,
`connect.telnyx.outgoing_callerid`, `connect.telnyx.user_callflow`
(+`_call`), `connect.telnyx.message_configuration`,
`connect.telnyx.texml` and `connect.telnyx.domain`.

Voice is integrated through **TeXML** — Telnyx's Twilio-compatible XML
translator: webhooks carry Twilio-shaped parameters (`CallSid`, `From`,
`To`, `CallStatus`, …) and Odoo answers with TeXML XML rendered by the
module's own builder (`models/texml_response.py` — no `twilio` python
dependency).

Everything the module contributes to the **shared** ledger models
carries a `telnyx_` prefix (fields *and* methods:
`on_telnyx_call_status`, `telnyx_render`, `get_telnyx_client_token`, …)
so it co-installs with connect_twilio, which owns the unprefixed names.

The exten dst-Reference mechanics, the callflow language list and the
E.164 caller-ID constraint are deliberate copies of the
Twilio/FreeSWITCH counterparts — **no shared mixin**; fixes must be
applied to all three modules (ADR-031/ADR-032).

### v1 scope exclusions (ADR-032, amended by ADR-033)

Attended transfer (`connect.call.transfer()`), Twilio-style caller-ID
validation, regions/edges, WhatsApp voice calling, rich RCS
cards/carousels. Call cost fetching is best-effort via detail records.
WhatsApp and RCS **messaging** are integrated (ADR-033).

---

## Models (connect_telnyx/models/)

### ai_assistant.py — `connect.telnyx.ai_assistant`

Manages Telnyx Voice AI Assistants through the v2 API. Odoo is authoritative:
account sync pushes local assistants and ignores unknown Telnyx assistants;
there is no remote Pull/import workflow (ADR-062). Stores the prompt, greeting,
model/voice/transcription settings, recording/memory switches and the Odoo
tool allowlist.

The always-on `register_call_request` webhook tool stores the qualified title,
summary and requested action as an internal note on the current `connect.call`.
Contact/CRM/Helpdesk tools remain individually gated by their assistant flags.

Receptionist routing fields: `receptionist_mode` (`personal` / `company`),
`transfer_enabled`, personal `manager`, company `transfer_callflows`,
`check_registration_before_transfer`, `warm_transfer_instructions`,
`transfer_tool_sid`, `domain`, `exten` / `exten_number`, and computed
`sip_uri`. Personal assistants target one manager; company assistants flatten
the configured callflows' `ring_users` into department-labelled human targets.

Odoo creates one Telnyx shared Transfer tool per configured assistant. The tool
uses dynamic `{{transfer_targets}}`, `{{telnyx_agent_target}}` as its caller,
premium voicemail detection with stop-transfer behavior, and a warm briefing
that includes confirmed identity, reason, context and next step. The variables
webhook checks each candidate's live telephony-credential registration status;
definitely offline devices are omitted, while API errors fall back to the
configured credential as an advisory unknown state.

Phone numbers and `connect.telnyx.exten` records route to assistants through
the existing TeXML applications using `<Connect><AIAssistant>`. An assistant
with a domain and extension is directly reachable from registered SIP/WebRTC
phones at `sip:<extension>@<subdomain>.sip.telnyx.com`.

Caller personalization performs a strict raw/E.164 lookup. A name is exposed
only when exactly one partner matches; multiple matches set the dynamic result
to ambiguous and expose no identity. The receptionist policy requires verbal
confirmation of a single candidate before treating the identity as verified,
and requires qualification of the call before any transfer.

Completed AI conversations are linked to `connect.call` by conversation and
Call Control IDs. Transcript and Telnyx Insight summary are stored on an
idempotent `connect.recording` row with `source = telnyx-ai`.

### texml_response.py — TeXML builder (no Odoo model)

`VoiceResponse`, `Gather`, `Dial` (+`sip()`/`number()`/`conference()`),
`pretty_xml()`, `apply_say_voice()` — an ElementTree-based mini-clone of
`twilio.twiml.voice_response` covering the verbs the module renders.
The finalizer adds the configured System Voice to every `<Say>` that does not
already have an explicit voice (ADR-055).

### settings.py - `_inherit = 'connect.settings'`

| Field | Type | Notes |
|-------|------|-------|
| `telnyx_api_key` | Char | Groups: `base.group_erp_manager` (ADR-025 pattern) |
| `display_telnyx_api_key` | Char | Masked display |
| `telnyx_public_key` | Char | Ed25519 public key for webhook verification |
| `telnyx_account_sid` | Char | TeXML Account SID — required for click-to-call |
| `telnyx_messaging_profile_id` | Char | Readonly, set by sync |
| `telnyx_outbound_voice_profile_id` | Char | Readonly; the profile every connection and TeXML app must carry to dial out |
| `telnyx_outbound_destinations` | Char | Comma-separated ISO country codes; written straight onto the profile whitelist (empty = all) |
| `telnyx_balance` | Char | Readonly |
| `telnyx_auto_sync` | Boolean | Default: True |
| `telnyx_verify_requests` | Boolean | Default: True |
| `telnyx_fetch_call_prices` | Boolean | |
| `telnyx_system_voice_language` | Selection | Dynamic language filter built from the cached catalog; default `en-US` |
| `telnyx_system_voice_provider` | Selection | Dynamic provider filter built from the cached catalog; default `aws` |
| `telnyx_system_voice` | Char | Telnyx voice ID chosen through a filtered server-backed autocomplete; default `Polly.Joanna` |
| `telnyx_tts_voices` | Text | Readonly JSON cache from `GET /v2/text-to-speech/voices` |

Methods: `get_telnyx_client()` (SDK client), `telnyx_sync()` (apps →
domains → numbers → caller IDs + messaging profile),
with persistent warning notifications for non-fatal optional-resource and
AI-assistant synchronization failures,
`_ensure_telnyx_account_sid()` (stores the account SID reported by
`GET /v2/whoami` as `organization_id`; a failure only warns),
`_ensure_telnyx_messaging_profile()`, `originate_call()` (core
dispatcher override for the `'telnyx'` key; originates via
`POST /texml/Accounts/{sid}/Calls` with the mandatory `ApplicationSid`
of the number application), `_sync_telnyx_tts_voices()` /
`telnyx_sync_tts_voices()` (cache/refresh the account voice catalog),
`telnyx_get_voice_options(language, provider, search, limit)` (bounded
autocomplete query over the cache), `telnyx_get_voice_label(voice_id)`
(readable current-value label),
`telnyx_apply_system_voice()` (finalize all missing Say voices),
`get_telnyx_balance()`,
`telnyx_check_call_failure(cause, sip_code)` (ADR-040: web-phone RPC
for unanswered outbound failures; verifies `GET /v2/balance` with
`sudo` and returns `{balance_blocked, message}` — Connect groups only,
the amount appears only for `connect.group_admin`, API errors are
swallowed to `connect.debug`), `write()`
(protected-field masking). Own standalone settings form view + menu via
`open_settings_form()`.

### call.py - `_inherit = 'connect.call'`

Fields: `telnyx_call_sid`, `telnyx_price`, `telnyx_price_unit`,
`telnyx_is_price_fetched`. Methods: `on_telnyx_call_status()` (adapter →
core `process_call_event`), `on_telnyx_vm_recording_status()`,
`telnyx_on_call_action()`, `save_telnyx_call_price()`,
`_fetch_telnyx_call_price()` (detail records),
`telnyx_fetch_call_prices_batch()` (cron).

### channel.py - `_inherit = 'connect.channel'`

`on_telnyx_call_status()` maps TeXML params (Twilio-shaped) to the
generic event dict → core `process_channel_event()`;
`telnyx_connect_notify()` desktop notification.

### message.py - `_inherit = 'connect.message'`

`telnyx_receive()` parses Telnyx v2 JSON envelopes (`message.received`,
`message.sent`, `message.finalized`); `send()` implements the core
abstract contract via `client.messages.send()`;
`telnyx_client_send()`; `_compute_direction()` override checks
`connect.telnyx.number`. **Known limitation:** co-installing
connect_twilio and connect_telnyx leaves the last-loaded module owning
`send()`/`_compute_direction` until a core dispatcher hook exists
(ADR-032 §9).

### recording.py - `_inherit = 'connect.recording'`

`on_telnyx_recording_status()` (TeXML recording callback + fetch of the
recording resource), `telnyx_prepare_data()` (maps `download_urls`,
`duration_millis`, and a resolvable API leg identifier). The webhook's TeXML
`CallSid` relation remains authoritative when the recording API returns an
unmatched UUID `call_leg_id`, so API enrichment cannot orphan the recording.
Raw Telnyx webhook debug payloads redact `RecordingUrl` before they are stored
in `connect.debug`; the unmodified URL is still used for recording playback.

### user.py - `_inherit = 'connect.user'`

A user holds up to two **telephony credentials** on the domain's
credential connection: one for a SIP hardphone, one for the web phone.
Telnyx generates `sip_username`/`sip_password` (readonly; the SIP
password is visible to the user for hardphone provisioning).

| Field | Type | Notes |
|-------|------|-------|
| `originate_provider` | Selection | `selection_add=[('telnyx', 'Telnyx')]` |
| `telnyx_exten` / `telnyx_exten_number` | M2O / related | registered in `_pbx_number_fields()` |
| `telnyx_outgoing_callerid` | M2O | |
| `telnyx_domain` | M2O | guarded default (install-order safe) |
| `telnyx_sip_enabled` / `telnyx_client_enabled` | Boolean | client default = `_telnyx_is_only_provider()` **and** a domain exists (a web phone needs one to register against) |
| `telnyx_sip_priority` / `telnyx_client_priority` | Selection | `1`/`2` |
| `telnyx_sip_ring_timeout` / `telnyx_client_ring_timeout` | Integer | |
| `telnyx_sip_credential_sid` / `telnyx_sip_username` / `telnyx_sip_password` | Char | hardphone credential, readonly (issued by Telnyx); username and password are shown in the clear with a copy button to the Connect groups |
| `telnyx_client_credential_sid` / `telnyx_client_username` | Char | web phone credential |
| `telnyx_uri` | Char | computed `<username>@sip.telnyx.com` |

Methods: `_create_telnyx_credential()` / `_ensure_telnyx_credentials()`
/ `delete_telnyx_credentials()` /
`action_regenerate_telnyx_sip_credential()` (Telnyx issues the SIP
username and password and accepts neither on create nor on update, so a
rotation deletes the credential and creates a new one — the username
changes too; `connect.group_admin` only); `telnyx_render()` +
`telnyx_render_sip/client/voicemail` (user_callflow chain, TeXML
`<Dial><Sip>`; user greeting/voicemail `<Say>` carries
`connect.user.language`/`voice`, with `en-US` / System Voice fallbacks —
ADR-037/ADR-055); `get_telnyx_client_token()` (JWT via
`telephony_credentials.create_token` + `sip_domain` for the web phone);
`get_user_by_telnyx_uri()`; `_telnyx_registration_status()` (`GET
/v2/sip_registration_status` with `credential_type=telephony_credential`) /
`_telnyx_transfer_target()` (priority-ordered registered SIP/WebRTC target,
advisory API-error fallback); `telnyx_on_call_action()` (ADR-057: the child
`DialCallStatus` takes precedence over the parent `CallStatus`; completed
destinations hang up, explicit failure statuses advance the user callflow,
and unknown statuses fail closed); callflow-managing constraints
(`_manage_telnyx_*`).

### number.py - `connect.telnyx.number`

Same shape as the Twilio number minus per-number webhook URLs: Telnyx
numbers are attached to the **number-routing TeXML app** (`Number Calls`,
`get_number_app()`, `phone_numbers.update(connection_id=…)`) and, when the
number supports SMS, to the messaging profile. A messaging failure is
logged and does not abort the sync — numbers without SMS capability are
still valid voice numbers.

Inbound calls therefore arrive on that app's webhook
(`/telnyx/webhook/texml/<app id>` → `route_call()`) and are dispatched by
`Called`/`To`: `render_inbound()` honours `destination`, falls back to an
extension carrying the same number, and never re-originates a call to the
dialled number. `connect.telnyx.domain.route_call()` delegates to
`render_inbound()` for numbers that are still attached to the domain
application, and refuses to dial out unless the caller is on our SIP
subdomain. `destination` Selection: `user` / `callflow` / `texml` /
`ai_assistant`. Numbers have no default flag; outbound defaults live on
`connect.telnyx.outgoing_callerid`.

The domain router accepts routing destinations both as
`sip:<extension>@<subdomain>.sip.telnyx.com` and as the bare
`<extension>@<subdomain>.sip.telnyx.com` form emitted by some Telnyx
callbacks. Real credential usernames routed back into the subdomain remain
blocked as loops. Call-progress mapping retains the initial channel parties,
direction, parent, status and duration when a later callback omits them
(ADR-054).

### outgoing_callerid.py - `connect.telnyx.outgoing_callerid`

Owned numbers only (no Telnyx validation API): `number` (E.164
constraint — copy of Twilio/FS, fix all three), `friendly_name`,
`is_default` (single default), `sid`, `sync()` from
`phone_numbers.list()`.

### callflow.py - `connect.telnyx.callflow` + `_choice`

Full copy of the Twilio callflow (Gather/Say/Dial/Record rendering via
the TeXML builder); optional `voice` overrides System Voice, otherwise the
callflow follows the global setting; language list is the shared BCP-47 copy.
Ring users dial the users' credential SIP URIs.

### exten.py - `connect.telnyx.exten`

dst-Reference mechanics (copy of Twilio/FS); `dst` selection:
`connect.user` / `connect.telnyx.callflow` / `connect.telnyx.texml` /
`connect.telnyx.ai_assistant`;
renders `connect.user` destinations via `telnyx_render()`.

### user_callflow.py, message_configuration.py

Same shape as the Twilio counterparts (`connect.telnyx.*`).

### whatsapp_sender.py - `connect.telnyx.whatsapp_sender` (ADR-033)

WhatsApp-enabled phone numbers synced from
`whatsapp.phone_numbers.list()` (+ profile subresource). Fields:
`number` (unique), `phone_number_id`, `waba_id`, `status`,
`display_name`, `quality_rating`, `calling_enabled` (info only),
editable `profile_*` (pushed via `profile.update`), `number_id`,
`no_sync`, `is_default`. Methods: `sync()`, `get_default_sender(user)`
(user pref → default flag → any), `send_whatsapp()` (freeform requires
an inbound message within 24h — else a template; creates
`connect.message` type `WhatsApp` + chatter), `chatter_post()`.

### whatsapp_template.py - `connect.telnyx.whatsapp_template` (ADR-033)

Meta-approved templates synced from `whatsapp.templates.list()`
(`telnyx_id`, `template_id`, `name`, `language`, `category`, `status`,
`rejection_reason`, raw `components`, extracted `body`).
`create_in_telnyx()` submits a body-only template for approval;
`_as_message_template()` / `_ordered_variable_values()` build the
send-time payload from `{{n}}` variables.

### rcs_agent.py - `connect.telnyx.rcs_agent` (ADR-033)

RCS agents synced read-only from `messaging.rcs.agents.list()`
(`agent_id` unique, `agent_name`, `enabled`, `profile_id`,
`is_default`). `send_rcs()` sends `content_message.text` with an
optional SMS fallback (`messages.rcs.send`) and logs a
`connect.message` type `RCS` + chatter.

### mail.py (ADR-033)

Adds `RCS` to `mail.message.message_type` and
`mail.notification.notification_type` (core adds `WhatsApp`).

### texml.py - `connect.telnyx.texml`

TeXML application management (analog of `connect.twilio.twiml`):
`code_type` `texml`/`texpy`/`model_method`, Jinja2 rendering, `exec`
sandbox exposing the module's TeXML builder, CRUD synced to
`texml_applications` (`sid` = app id).

### domain.py - `connect.telnyx.domain`

The Twilio SIP-domain analog (ADR-032 §3). One record manages:

- a **credential connection** (`sid`; generated connection-level
  user/password, stored username only) hosting per-user telephony
  credentials. Created and kept with `sip_uri_calling_preference =
  'internal'` (Telnyx returns `403` to `sip:<credential>@sip.telnyx.com`
  otherwise) and with the account's outbound voice profile (no outbound
  call is allowed without one);
- the **routing TeXML app** (`application`, default `get_domain_app()`)
  whose `inbound.sip_subdomain` = `subdomain`
  (`sip_subdomain_receive_settings='only_my_connections'`).

The subdomain is the **inbound** side only: everything dialled at it is
handed to the routing application, so credentials are rung at
`sip.telnyx.com` (`connect.user._telnyx_credential_uri()`) and
`route_call()` refuses a credential leg to break the loop.

`route_call()` routes web-phone calls: exten match → render; a dialled
`+E164` from a known PBX user → `originate_external_call()` (TeXML
`<Dial><Number>` with the user's caller ID and `record_calls` policy), and an
unknown caller is refused. The originating user is resolved consistently from
`Caller`, `From`, or `CallerId`, because Telnyx may omit `Caller` for the
web-phone SIP leg. A PSTN leg for one of our numbers is delegated to
`connect.telnyx.number.render_inbound()`. `sync()` follows the Twilio
rules (never import Telnyx-only, create Odoo-only, update common).

---

## Controllers (connect_telnyx/controllers/telnyx_webhooks.py)

All routes under `/telnyx/webhook/`, `auth='public'`, POST. Signature
validation: Ed25519 over the raw body
(`telnyx.lib.webhook_verification`), toggled by
`telnyx_verify_requests`, key = `telnyx_public_key`. The exact request bytes
are cached in `ir.http._pre_dispatch` before Odoo parses TeXML form data;
reconstructed or canonicalized form bodies are never accepted. Invalid Dial
action callbacks fail closed with a silent `<Hangup/>` response so no security
error is played into a remaining live leg (ADR-056).

| Route | Description |
|-------|-------------|
| `/telnyx/webhook/domain` | Web-phone/SIP-subdomain call routing |
| `/telnyx/webhook/callstatus` | Call status callback |
| `/telnyx/webhook/number` | Inbound call to a number |
| `/telnyx/webhook/callflow/<id>/gather` | Callflow gather result |
| `/telnyx/webhook/vm_recordingstatus` | Voicemail recording callback |
| `/telnyx/webhook/<model>/call_action/<id>` | Dial action (dispatches to `telnyx_on_call_action` for `connect.user`) |
| `/telnyx/webhook/recordingstatus` | Recording status callback |
| `/telnyx/webhook/callaction` | Generic call action |
| `/telnyx/webhook/texml/<id>` | TeXML app voice request |
| `/telnyx/webhook/message` | Messaging v2 JSON events |
| `/telnyx/webhook/assistant/<id>/variables` | Signed caller context and memory configuration |
| `/telnyx/webhook/assistant/<id>/tool/<name>` | Token-authenticated allowlisted Odoo tool |
| `/telnyx/webhook/assistant/insights` | Signed conversation summary delivery |

---

## Wizards

### sms_composer.py — inherits `sms.composer`

Same as the Twilio one (raw SQL over `connect_telnyx_number`); subject
to the co-installation limitation of ADR-032 §9.

### whatsapp_composer.py - `connect.telnyx.whatsapp_composer` (ADR-033)

Transient wizard: sender (default via `get_default_sender`), phone,
approved template + variables JSON with live body preview, freeform
body. Mirrors the Twilio composer UX.

### rcs_composer.py - `connect.telnyx.rcs_composer` (ADR-033)

Transient wizard: agent (default via `get_default_agent`), phone, body,
SMS-fallback toggle + fallback sender (defaults to the default outgoing
caller ID).

---

## Security

Access matrix mirrors connect_twilio (ADR-032 §13): PBX config models —
user read / admin full / webhook read; `user_callflow(_call)` — user
read / admin full; `message_configuration` — admin only;
`outgoing_callerid` webhook has **no write** row (no validation
callback); WhatsApp senders — user R / admin CRUD / webhook R;
WhatsApp templates and RCS agents — user R / admin CRUD; the WhatsApp
and RCS composers — user CRUD (transients). Plus the `sms.composer`
user grant.

---

## Data

- `data/texml.xml` — `SIP Domain Calls` routing app (model_method →
  `connect.telnyx.domain.route_call`), `Number Calls` app (model_method →
  `connect.telnyx.number.route_call`, the application every number is
  attached to), `Reject`, `Connection Failed`.
- `data/ir_cron.xml` — `telnyx_fetch_call_prices_batch()` every 5 min.

---

## Views & Menu

Standalone Telnyx settings form; list/form views for numbers, extens,
callflows, caller IDs, TeXML apps, domains, message configuration;
core user form/list extended with the Telnyx Phone tab and columns;
`connect.call` form gets a Telnyx page. Menu: **Connect > Telnyx**
(seq 50): Numbers, Extensions, Call Flows, Outgoing Caller IDs, TeXML
Apps, SIP Domains, Messages (Messages, Message Configuration,
WhatsApp Senders, WhatsApp Templates, RCS Agents — admin),
Configuration > Settings.

---

## Frontend (connect_telnyx/static/src/)

Port of the Twilio phone widget to **@telnyx/webrtc** (vendored UMD
bundle `lib/telnyx-webrtc.js`, global `TelnyxWebRTC.TelnyxRTC`):

- `js/main.js` — fetches `get_telnyx_client_token()`
  (`{token, sip_domain}`), registers Telnyx-unique registry keys
  (`ConnectTelnyxPhoneService`, `connectTelnyxPhoneSysTray`,
  `connectTelnyxPhone`).
- `components/phone/phone/phone.js` — `TelnyxSession` adapter exposes a
  Twilio-Device-like session API over a TelnyxRTC Call
  (`answer`/`hangup`/`muteAudio`/`dtmf`, custom X- headers →
  `customParameters`); `telnyx.notification` `callUpdate` states drive
  the `accept`/`disconnect`/`cancel` handlers. Outgoing calls dial
  `sip:<number>@<subdomain>.sip.telnyx.com` so Odoo routes them. Token
  refresh re-initializes the client. Remote audio attaches to
  `#connect-telnyx-remote-audio`. Unanswered outbound failures raise a
  warning notification with the mapped hangup cause (busy / rejected /
  number not found / generic `cause` + SIP code; user-initiated
  `ORIGINATOR_CANCEL`/`NORMAL_CLEARING` stay silent); the ambiguous
  404/`UNALLOCATED_NUMBER` case additionally calls
  `connect.settings.telnyx_check_call_failure()` and shows a sticky
  danger notification when the account balance is exhausted (ADR-040).
  Odoo's error-handler registry consumes only the SDK's expected
  `StaleRequestError` cancellation when a background tab resumes and the
  signaling socket generation changes; other client and media errors keep
  their normal handling (ADR-053).
- Mail integration: `telnyx-sms-reply` / `telnyx-whatsapp-reply` /
  `telnyx-rcs-reply` chatter actions, the Notification icon patch for
  the `WhatsApp`/`RCS` types, and a WhatsApp *Message* button on the
  phone field widget (ADR-033).
- The rest (contacts/favorites/tray components, phone field widget,
  actions service) is the Twilio code with renamed registry keys and the
  `telnyx_exten_number` field. The **Calls history tab** and the
  **active-calls systray widget** are no longer copied here — they are
  imported from / registered by core `connect`
  (`@connect/components/calls/calls`, `connect/services/active_calls`).

---

## Dependencies Summary

```
connect_telnyx
  depends: ['connect']
  python:  ['telnyx', 'nacl']
```
