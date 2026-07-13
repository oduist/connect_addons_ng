# Connect Telnyx Module Specification

## Module Info

- **Name:** Oduist Connect Telnyx
- **Technical:** `connect_telnyx`
- **Version:** 19.0.1.0.0
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

Manages Telnyx Voice AI Assistants through the v2 API. Stores the prompt,
greeting, model/voice/transcription settings, recording/memory switches and
the Odoo tool allowlist. Unknown remote assistants are imported by account
sync; once imported, Odoo configures its signed dynamic-variables webhook and
per-assistant tool endpoints. Phone numbers route to assistants through the
existing TeXML application using `<Connect><AIAssistant>` (ADR-034).

Completed AI conversations are linked to `connect.call` by conversation and
Call Control IDs. Transcript and Telnyx Insight summary are stored on an
idempotent `connect.recording` row with `source = telnyx-ai`.

### texml_response.py — TeXML builder (no Odoo model)

`VoiceResponse`, `Gather`, `Dial` (+`sip()`/`number()`/`conference()`),
`pretty_xml()` — an ElementTree-based mini-clone of
`twilio.twiml.voice_response` covering the verbs the module renders.

### settings.py - `_inherit = 'connect.settings'`

| Field | Type | Notes |
|-------|------|-------|
| `telnyx_api_key` | Char | Groups: `base.group_erp_manager` (ADR-025 pattern) |
| `display_telnyx_api_key` | Char | Masked display |
| `telnyx_public_key` | Char | Ed25519 public key for webhook verification |
| `telnyx_account_sid` | Char | TeXML Account SID — required for click-to-call |
| `telnyx_messaging_profile_id` | Char | Readonly, set by sync |
| `telnyx_balance` | Char | Readonly |
| `telnyx_auto_sync` | Boolean | Default: True |
| `telnyx_verify_requests` | Boolean | Default: True |
| `telnyx_fetch_call_prices` | Boolean | |

Methods: `get_telnyx_client()` (SDK client), `telnyx_sync()` (apps →
domains → numbers → caller IDs + messaging profile),
`_ensure_telnyx_messaging_profile()`, `originate_call()` (core
dispatcher override for the `'telnyx'` key; originates via
`POST /texml/Accounts/{sid}/Calls`), `get_telnyx_balance()`, `write()`
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
`duration_millis`, `call_leg_id`).

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
| `telnyx_sip_enabled` / `telnyx_client_enabled` | Boolean | client default = `_telnyx_is_only_provider()` |
| `telnyx_sip_priority` / `telnyx_client_priority` | Selection | `1`/`2` |
| `telnyx_sip_ring_timeout` / `telnyx_client_ring_timeout` | Integer | |
| `telnyx_sip_credential_sid` / `telnyx_sip_username` / `telnyx_sip_password` | Char | hardphone credential |
| `telnyx_client_credential_sid` / `telnyx_client_username` | Char | web phone credential |
| `telnyx_uri` | Char | computed `<username>@sip.telnyx.com` |

Methods: `_create_telnyx_credential()` / `_ensure_telnyx_credentials()`
/ `delete_telnyx_credentials()`; `telnyx_render()` +
`telnyx_render_sip/client/voicemail` (user_callflow chain, TeXML
`<Dial><Sip>`; user greeting/voicemail `<Say>` carries
`connect.user.language`/`voice`, fallbacks `en-US` / `Polly.Joanna` —
ADR-037); `get_telnyx_client_token()` (JWT via
`telephony_credentials.create_token` + `sip_domain` for the web phone);
`get_user_by_telnyx_uri()`; `telnyx_on_call_action()`; callflow-managing
constraints (`_manage_telnyx_*`).

### number.py - `connect.telnyx.number`

Same shape as the Twilio number minus per-number webhook URLs: Telnyx
numbers are attached to the domain's routing TeXML app
(`phone_numbers.update(connection_id=…)`) and to the messaging profile;
inbound calls arrive on the shared `/telnyx/webhook/number` route and
are dispatched by `Called`/`To` (`route_call()` → `render()`).
`destination` Selection: `user` / `callflow` / `texml`. Numbers have no
default flag; outbound defaults live on `connect.telnyx.outgoing_callerid`.

### outgoing_callerid.py - `connect.telnyx.outgoing_callerid`

Owned numbers only (no Telnyx validation API): `number` (E.164
constraint — copy of Twilio/FS, fix all three), `friendly_name`,
`is_default` (single default), `sid`, `sync()` from
`phone_numbers.list()`.

### callflow.py - `connect.telnyx.callflow` + `_choice`

Full copy of the Twilio callflow (Gather/Say/Dial/Record rendering via
the TeXML builder); `voice` default `Polly.Joanna`; language list is the
shared BCP-47 copy. Ring users dial the users' credential SIP URIs.

### exten.py - `connect.telnyx.exten`

dst-Reference mechanics (copy of Twilio/FS); `dst` selection:
`connect.user` / `connect.telnyx.callflow` / `connect.telnyx.texml`;
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
  credentials;
- the **routing TeXML app** (`application`, default `get_domain_app()`)
  whose `inbound.sip_subdomain` = `subdomain`
  (`sip_subdomain_receive_settings='only_my_connections'`).

`route_call()` routes web-phone calls: exten match → render; `+E164` →
`originate_external_call()` (TeXML `<Dial><Number>` with the user's
caller ID). `sync()` follows the Twilio rules (never import
Telnyx-only, create Odoo-only, update common).

---

## Controllers (connect_telnyx/controllers/telnyx_webhooks.py)

All routes under `/telnyx/webhook/`, `auth='public'`, POST. Signature
validation: Ed25519 over the raw body
(`telnyx.lib.webhook_verification`), toggled by
`telnyx_verify_requests`, key = `telnyx_public_key`.

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
  `connect.telnyx.domain.route_call`), `Reject`, `Connection Failed`.
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
  `#connect-telnyx-remote-audio`.
- Mail integration: `telnyx-sms-reply` / `telnyx-whatsapp-reply` /
  `telnyx-rcs-reply` chatter actions, the Notification icon patch for
  the `WhatsApp`/`RCS` types, and a WhatsApp *Message* button on the
  phone field widget (ADR-033).
- The rest (calls/contacts/favorites/tray components, active-calls
  service, phone field widget, actions service) is the Twilio code with
  renamed registry keys and the `telnyx_exten_number` field.

---

## Dependencies Summary

```
connect_telnyx
  depends: ['connect']
  python:  ['telnyx', 'nacl']
```
