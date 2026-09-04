# Connect Twilio Module Specification

## Module Info

- **Name:** Oduist Connect Twilio
- **Technical:** `connect_twilio`
- **Version:** 19.0.2.3.0
- **Depends:** `connect`
- **Python deps:** `twilio`
- **Application:** False
- **License:** Other proprietary
- **post_init_hook:** stamps the module install date and refreshes the Oduist
  license status (`update_license_status`)
- **Migrations:** `migrations/19.0.2.0.1/post-migration.py` — drops the obsolete
  `is_default` column from `connect_twilio_number` (outbound defaults are owned
  by `connect.twilio.outgoing_callerid`)

## Overview

The `connect_twilio` module extends the core `connect` module with Twilio-specific
functionality. The shared ledger models (`connect.call`, `connect.channel`,
`connect.message`, `connect.recording`, `connect.user`, `connect.settings`) are
extended via `_inherit`; since ADR-031 the module also **owns its PBX configuration
models** as independent `connect.twilio.*` models: `connect.twilio.exten`,
`connect.twilio.callflow` (+`_choice`), `connect.twilio.number`,
`connect.twilio.outgoing_callerid`, `connect.twilio.user_callflow` (+`_call`) and
`connect.twilio.message_configuration`. The formerly-core `connect.twiml` and
`connect.domain` models were renamed `connect.twilio.twiml` and
`connect.twilio.domain` for naming consistency. `connect.whatsapp_sender` and
`connect.message_content_template` keep their names.

The exten dst-Reference mechanics, the callflow language list and the E.164
caller-ID constraint are deliberate copies of the FreeSWITCH counterparts —
**no shared mixin**; fixes must be applied in both modules (ADR-031).

This module handles: Twilio REST API client, webhook handlers for calls/messages/recordings,
TwiML generation, SIP domain management, WhatsApp integration, Twilio Voice SDK (frontend),
and Twilio number/callerID synchronization.

OpenAI transcription is NOT in this module - it lives in core `connect` because it is
technology-agnostic. The SMS composer (`sms.composer` inherit) lives HERE since
ADR-031, implementing the core abstract `connect.message.send()` contract.

---

## Models (connect_twilio/models/) - ledger models use _inherit; PBX configuration models are own `connect.twilio.*` models

### 1. settings.py - `_inherit = 'connect.settings'`

Extends core settings with Twilio API credentials, client management, and sync.

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `account_sid` | Char | Twilio Account SID |
| `auth_token` | Char | Groups: `base.group_erp_manager` — never grant `connect.group_webhook` (the public-webhook identity); signature validation reads it via `sudo()` (ADR-025) |
| `display_auth_token` | Char | Masked display |
| `twilio_api_key` | Char | |
| `twilio_api_secret` | Char | Groups: `base.group_erp_manager` |
| `display_twilio_api_secret` | Char | Masked display |
| `twilio_balance` | Char | Readonly |
| `twilio_region` | Selection | `us1`, `ie1`, `au1` |
| `twilio_edge` | Selection | Twilio edge location |
| `twilio_auto_sync` | Boolean | Default: True |
| `twilio_verify_requests` | Boolean | Default: True |
| `fetch_call_prices` | Boolean | |

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `get_client()` | Create and return Twilio REST client instance |
| `sync()` | Full sync of all Twilio resources (numbers, callerIDs, domains, etc.) |
| `get_media_auth(media_url)` | `(account_sid, auth_token)` for `*.twilio.com` media, `None` for anything else — an External Storage bucket must not receive the Twilio token (ADR-060) |
| `originate_call()` | Override of the core dispatcher: when `_get_originate_provider(user)` is not `'twilio'`, falls through to `super()`; otherwise initiates the outbound call via the Twilio API. The `From` of an internal originate comes from `connect.user.twilio_caller_id()` (ADR-058). With `whatsapp_call=True` the WhatsApp identity goes on the inner `<Dial callerId="whatsapp:…"><WhatsApp>`, never on the outer leg's `From` — Twilio accepts the create, reports `From=None` and ends the call as busy in the same second, so the `<WhatsApp>` verb never runs. The channel it creates records `call_type` (`whatsapp`/`phone`) explicitly, because nothing on that leg lets the status webhook infer it |
| `get_external_call_route()` | Return TwiML route for external calls |
| `compute_sip_uri(user)` | Return `sip:<uri>` for the current user's `connect.user` (core dispatcher hook) |
| `get_twilio_balance()` | Fetch account balance from Twilio API |
| `_reset_twilio_edge()` | Onchange: reset edge when region changes |
| `write()` | Override: handle protected field masking for auth_token and api_secret |

The Twilio settings are edited through the module's **own standalone settings
form view** (menu Twilio → Configuration → Settings), opened via the core
parametrized `open_settings_form()` — no notebook pages are injected into the
core settings form.

---

### 2. call.py - `_inherit = 'connect.call'`

Extends core call with Twilio CallSid tracking, pricing, and webhook handling.

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `call_sid` | Char | Twilio CallSid |
| `price` | Float | Call cost |
| `price_unit` | Char | Currency code |
| `price_currency` | Char | Currency symbol |
| `is_price_fetched` | Boolean | Whether price has been retrieved |

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `on_call_status()` | Twilio webhook handler: process call status callbacks |
| `on_vm_recording_status()` | Twilio webhook handler: voicemail recording complete |
| `save_call_price()` | Store CallSid for deferred price fetching |
| `_fetch_call_price_from_api()` | Fetch call price from Twilio REST API |
| `fetch_call_prices_batch()` | Cron: batch fetch prices for unfetched calls |
| `transfer()` | Transfer call using Twilio Conference/SIP REFER |

---

### 3. channel.py - `_inherit = 'connect.channel'`

Twilio webhook adapter for the core channel ledger. **Adds no fields** — the
`sid` / `parent_sid` columns it fills are core `connect.channel` fields; this
file only maps Twilio webhook params onto them and implements the Twilio
handlers for the core softphone recording RPCs.

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `on_call_status()` | Twilio webhook: map the params via `_map_twilio_params()` and delegate to the core `process_channel_event()` |
| `_map_twilio_params()` | Map Twilio webhook params to the generic channel event dict (SIDs, caller/called, direction, status, duration, `call_type` phone/whatsapp) |
| `_strip_exten_plus()` | Twilio E.164-prefixes a bare extension used as caller ID (`100` comes back as `+100`); map it back when a `connect.twilio.exten` matches |
| `_twilio_recording_call_sids()` / `_twilio_active_recording()` | Resolve which leg (this one or its parent chain) carries a live recording — see *Runtime softphone recording control* below |
| `_softphone_recording_state_twilio()` / `_softphone_recording_start_twilio()` / `_softphone_recording_stop_twilio()` | Twilio handlers for the core softphone recording RPCs |
| `connect_notify()` | Desktop notification for incoming SIP/Client calls |
| `transfer()` | Channel-level transfer via Twilio API |

---

### 4. message.py - `_inherit = 'connect.message'`

Extends core message with Twilio message handling - implements the abstract `send()` method.

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `message_sid` | Char | **Core field** (`connect.message`) — re-declared here as a plain Char; not required |
| `account_sid` | Char | Twilio Account SID |
| `messaging_service_sid` | Char | Twilio Messaging Service SID |

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `receive()` | Twilio webhook: process incoming SMS/WhatsApp messages. Runs as the webhook user, so the `connect.twilio.message_configuration` lookup is `sudo()`d — that model is admin-only by design, and reading it unprivileged raised an `AccessError` the handler's own `except` swallowed, silently discarding the message while still answering 200 (so Twilio never retried) |
| `send()` | **Implements abstract:** Send message via Twilio API. Dispatch guard: when `connect.settings._get_message_provider()` is not `'twilio'`, falls through to `super()` (co-installation with other messaging providers, e.g. `connect_bird`). |
| `client_send()` | Low-level: `client.messages.create()` wrapper |
| `action_retry()` | Re-send `failed` messages through `send()` (same recipient/body/target, original `from_number` as caller ID); non-`failed` records are skipped |
| `_compute_direction()` | Override: check against Twilio-owned numbers to determine direction |

---

### 5. recording.py - `_inherit = 'connect.recording'`

Twilio webhook/API adapter for the core recording ledger. **Adds no fields** —
`sid` and `call_sid` are core `connect.recording` fields; this file fills them
from Twilio webhook params and API fetches.

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `on_recording_status()` | Twilio webhook: build the record values from the callback params (SIDs, duration, status, channel/call/partner links), fetch the recording details from the Twilio API, then create the `connect.recording` row via the standard `create()` |
| `prepare_data()` | Map a Twilio API recording object into recording field values (incl. channel/call resolution by `call_sid`) |
| `sync()` | Refresh existing recording rows from the Twilio API |

**Notes:**
- Transcription methods (`transcribe_recording()`, `make_summary()`, etc.) are NOT here.
  They live in core `connect` because OpenAI transcription is technology-agnostic.
- This module only handles Twilio-specific recording webhook processing and SID tracking.

### Runtime softphone recording control

`connect.channel` is extended with Twilio handlers for the core softphone
recording RPCs. The phone widget sends provider `twilio` and the active
`CallSid`; the handler resolves the channel row, verifies participant/admin
access through core helpers, and uses Twilio's Recording API to start/stop
recording. Runtime state is stored on the shared channel control fields
(`recording_state`, `recording_control_ref`, `recording_control_error`) while
completed artifacts continue to enter `connect.recording` through the Twilio
recording status webhook.

Live state is read from Twilio, never inferred from configuration. When the
channel carries no control state of its own, `_softphone_recording_state_twilio`
calls `_twilio_active_recording()`, which walks `_twilio_recording_call_sids()`
— this leg and then its parent chain — lists each leg's recordings and keeps
the ones whose `status` is `in-progress`. The filtering is done here, in
Python: `CallRecordingList.list()` filters by date only, and passing it
`status=` raises `TypeError`. The parent hop matters because a
callflow emits `<Dial record='record-from-answer-dual'>` on the inbound leg
while the softphone holds the client child leg; without it a recorded callflow
call reports `off`. `_softphone_recording_stop_twilio` resolves the same way, so
stop targets the leg that actually carries the recording and falls back to
`channel.sid` + `Twilio.CURRENT` only when no live recording is found. Lookup
failures are logged and degrade to `off` rather than breaking the widget.

The phone renders `off` as a purple circular badge with a white dot and `REC`
label, and `on` as a purple `fa-stop-circle` active action; transitions use a
spinner. The button exposes a dynamic accessible label and `aria-pressed`.
`connect.user.record_calls=False` keeps automatic recording off but does not
hide the manual start action, and it no longer influences the reported state.

**Painting the state before Twilio can answer.** With
`<Dial record="record-from-answer">` the recording does not exist until the far
end picks up, and the API needs a further moment to list it, so a single sample
at `accept` always landed in the gap and left the button offering *Start
Recording* for a call that was being recorded. Two mechanisms cover the window:

- `applyExpectedRecordingState()` paints the button at `accept` from the
  `record_calls` value returned by `get_client_token()`. That flag is what
  actually decides recording in every path the web phone uses — the caller's own
  `connect.user.record_calls` for outgoing (`connect.settings.originate_call`)
  and the callee's for incoming (the user dial TwiML and the SIP domain
  handler) — so the widget owner's own flag governs both directions.
- `syncRecordingState()` then polls (1.5s interval, up to a minute — `accept`
  fires when the leg reaches Twilio, not when the far end answers, so the wait
  is however long the phone rings) and overwrites that optimistic state only
  once Twilio gives a real answer. An `off` with no recording reference counts
  as *not yet settled* and keeps polling; anything else ends the loop. The
  error state is reported only when no CallSid ever arrived.

`_twilio_active_recording()` accepts the three non-terminal statuses, not just
`in-progress`: on a live call Twilio reports a running recording as
`processing` with `duration -1`. Twilio remains the sole authority on recording
state — the expected state only decides what is painted before the API can
answer.

---

### 6. user.py - `_inherit = 'connect.user'`

Extends core user with Twilio SIP credentials, client tokens, and TwiML rendering.

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `username` | Char | PBX username, `UNIQUE`, alphanumeric. **Not field-level required** (co-installation fix): a constraint on `sip_enabled`/`client_enabled`/`username`/`domain` requires username+domain only when the Twilio SIP or web phone is enabled |
| `originate_provider` | Selection | `selection_add=[('twilio', 'Twilio')]` on the core field |
| `message_provider` | Selection | `selection_add=[('twilio', 'Twilio')]` on the core field |
| `twilio_exten` | Many2one | `connect.twilio.exten`, readonly |
| `twilio_exten_number` | Char | Related `twilio_exten.number`, stored; registered in `_pbx_number_fields()` |
| `twilio_outgoing_callerid` | Many2one | `connect.twilio.outgoing_callerid` |
| `sid` | Char | Twilio SIP credential SID |
| `password` | Char | SIP password, groups restricted |
| `domain` | Many2one | `connect.twilio.domain` (guarded default: first non-BYOC domain, skipped while the table does not exist yet during install) |
| `sip_enabled` | Boolean | |
| `sip_priority` | Selection | `1` or `2` |
| `sip_ring_timeout` | Integer | Seconds |
| `client_enabled` | Boolean | Default: `_twilio_is_only_provider()` — True only when Twilio is the sole installed telephony module; in multi-provider databases the admin enables the Twilio web phone explicitly per user |
| `client_priority` | Selection | `1` or `2` |
| `client_ring_timeout` | Integer | Seconds |
| `uri` | Char | Computed: `user@domain` |
| `connect_uri` | Char | Computed: with edge prefix |
| `application` | Many2one | `connect.twilio.twiml` |
| `whatsapp_sender_id` | Many2one | `connect.whatsapp_sender`; selectable senders must be synchronized and `ONLINE` |
| `twilio_edge` | Selection | Twilio edge location |

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `_create_sip_account()` | Create SIP credential on Twilio |
| `_import_existing_sip_credential()` | Import existing credential from Twilio |
| `_update_sip_password()` | Update SIP password on Twilio |
| `delete_sip_account()` | Delete SIP credential from Twilio |
| `generate_twilio_password()` | Generate strong random password |
| `render()` | Main TwiML rendering: dispatches to client/sip/voicemail. With a ledger call it walks the callflows through `connect.twilio.user_callflow_call`; without one (click-to-call, rendered before the channel exists) it emits a single `<Dial>` and carries the already-dialed ids in the action URL |
| `render_client()` | Generate TwiML `<Dial><Client>`; for a bare extension caller ID it adds a `From` `<Parameter>` (Twilio hands the callee `+101`; the web phone prefers the parameter). Other caller IDs reach the browser as Twilio's own `From` (ADR-058) |
| `render_sip()` | Generate TwiML `<Dial><Sip>` |
| `render_voicemail()` | Generate TwiML `<Record>` for voicemail |
| `get_greeting_message()` / `get_voicemail_prompt()` | `<Say>` the user prompts with `language`/`voice` from `connect.user` (fallbacks `en-US` / `Woman`, ADR-037) |
| `get_client_token()` | Generate JWT for Twilio Voice SDK. Returns `record_calls` alongside the token so the widget can paint the expected recording state at answer with no extra round trip (see *Runtime recording control* below); returns `{'token': False}` for a user outside the Connect groups |
| `get_client_identity()` | Return SIP identity string |
| `twilio_caller_id()` | Caller ID for calls this user places: the extension, else `twilio_outgoing_callerid`, else the default outgoing caller ID, else the client identity `client:<username>@<domain>` — an empty caller ID makes Twilio substitute an arbitrary number (ADR-058) |
| `_get_sip_uri()` | Compute SIP URI |
| `_manage_sip_callflow()` | Auto-manage SIP callflow entries |
| `_manage_client_callflow()` | Auto-manage client callflow entries |
| `_manage_voicemail_enabled()` | Constrains: create/remove the `voicemail` user-callflow step when `voicemail_enabled` changes |
| `_manage_channel_callflow()` | Shared helper: create/update/remove the SIP or client user-callflow step for the channel priority |
| `_restrict_sip_domain_change()` | Onchange: forbid changing the SIP domain while a SIP account (SID) exists — disable SIP first |
| `create()` | Override: when `sip_enabled` with a password, creates the SIP **credential** on Twilio and masks the password. It does **NOT** create an extension — extensions come from the manual `create_twilio_extension()` button |
| `create_twilio_extension()` | Manual action (the **Twilio Extension** button on the user form): create/edit this user's `connect.twilio.exten` |
| `render_voicemail_prompt()` | Render the user's `voicemail_prompt` as a Jinja2 template (`{'user': self}` context) |
| `get_user_by_uri()` | Lookup `connect.user` by a `sip:`/`client:` URI's username; falls through to `super()` when nothing matches |
| `_twilio_is_only_provider()` | True when no other telephony module (`connect_freeswitch`/`connect_asterisk`) is installed — drives the `client_enabled` default |
| `_get_caller_id()` | Caller ID for a rendered dialplan: `twilio_caller_id()` of the calling user, or the raw `Caller` when it maps to no PBX user |
| `_get_caller_name()` | Caller name for the web-phone `<Client>` parameter: the calling PBX user's name, else the `CallerName` param |
| `write()` | Override: handle SIP credential updates |
| `unlink()` | Override: cleanup SIP account on Twilio |
| `on_call_action()` | `<Dial>` action webhook: records the dialed callflows, stops on a leg that was answered/canceled (`DialCallStatus`), otherwise renders the next device |
| `_is_call_action_final()` | Whether the callflow walk must stop at this `<Dial>` action callback: terminal parent `CallStatus`, or a `DialCallStatus` other than busy/no-answer/failed |
| `_get_dial_action_url()` / `_parse_done_callflows()` | Build/read the `done_callflows=` marker the action URL carries |
| `_record_done_callflows()` / `_clear_done_callflows()` | Fold the marker into `connect.twilio.user_callflow_call` and drop the bookkeeping when the walk ends |

---

### 7. number.py - `connect.twilio.number` (own model, ADR-031)

Twilio inbound DIDs — full standalone model (formerly a `connect.number`
extension) with Twilio SID, webhook URLs, sync and call routing.

**Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `phone_number` | Char | Required (no uniqueness constraint) |
| `friendly_name` | Char | |
| `destination` | Selection | `user`, `callflow`, `twiml` |
| `callflow` | Many2one | `connect.twilio.callflow` |
| `user` | Many2one | `connect.user` |
| `twiml` | Many2one | `connect.twilio.twiml` |
| `is_ignored` | Boolean | "Ignored" — exclude the number from Connect routing/management |
| `sid` | Char | Twilio Phone Number SID |
| `voice_url` | Char | Computed webhook URL |
| `voice_fallback_url` | Char | Computed |
| `voice_status_url` | Char | Computed |
| `message_url` | Char | Computed |
| `message_fallback_url` | Char | Computed |

**Methods:**

| Method | Description |
|--------|-------------|
| `sync()` | Sync phone numbers from Twilio API |
| `update_twilio_number()` | Push webhook configuration to Twilio |
| `_get_twilio_urls()` | Compute webhook URLs for this number |
| `write()` | Override: push changes to Twilio on save |
| `render()` / `route_call()` | Route inbound call to the destination (TwiML response) |

---

### 8. outgoing_callerid.py - `connect.twilio.outgoing_callerid` (own model, ADR-031)

Outbound caller IDs — full standalone model (formerly a
`connect.outgoing_callerid` extension) with Twilio validation and sync.

**Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Computed: friendly_name + number |
| `friendly_name` | Char | Required |
| `number` | Char | Required, `UNIQUE`, must start with `+` (E.164 constraint — duplicated in connect_freeswitch, fix both) |
| `callerid_type` | Selection | Required, default `outgoing_callerid`. `outgoing_callerid` ("CallerID") = a verified external number; `number` ("DID Number") = a Twilio-owned incoming phone number mirrored here as a usable caller ID |
| `status` | Char | Validation status (`not validated` / `validated` / `validation failed`); `number`-type records skip validation |
| `is_default` | Boolean | Only one default allowed; an `outgoing_callerid`-type record must be `validated` before it can become the default (`_check_default`) |
| `callerid_users` | One2many | `connect.user` via `twilio_outgoing_callerid` |
| `sid` | Char | Twilio OutgoingCallerID / IncomingPhoneNumber SID |
| `validation_code` | Char | Twilio validation code |

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `sync()` | Sync both batches: `sync_outgoing_callerid('outgoing_callerid')` then `sync_outgoing_callerid('number')` |
| `sync_outgoing_callerid(callerid_type)` | Sync one `callerid_type` **batch** from the matching Twilio list (`outgoing_caller_ids` vs `incoming_phone_numbers`): create/update local rows, push friendly-name changes back, and remove local rows of that type whose SID is gone from Twilio |
| `validate()` | Initiate Twilio phone validation for an `outgoing_callerid`-type record. **Requires `twilio_region == 'us1'`** — Twilio supports outgoing caller IDs in US1 only; an already-verified number is re-imported via `sync()` |
| `update_status()` | Webhook: validation status callback — matches the number against `callerid_type = 'outgoing_callerid'` records only and sets `validated`/`validation failed` |
| `_check_default()` | Constrains: `is_default` on an `outgoing_callerid`-type record requires `status == 'validated'` |
| `_change_number_friendly_name()` | Constrains: push the friendly name to Twilio (`outgoing_caller_ids` for `outgoing_callerid` type, the linked `connect.twilio.number` for `number` type) |
| `create()` | Override: new `outgoing_callerid`-type records start at `status = 'not validated'` (skipped with `skip_validation` context, e.g. during sync) |
| `unlink()` | Override (only when `twilio_auto_sync` is on): deleting a `callerid_type = 'number'` record **raises** — Twilio numbers must be removed in the Twilio Console and re-synced; `outgoing_callerid`-type records are also deleted from Twilio |

---

### 9. callflow.py - `connect.twilio.callflow` + `connect.twilio.callflow_choice` (own models, ADR-031)

IVR configuration and TwiML Gather rendering — full standalone models (formerly
`connect.callflow`/`connect.callflow_choice` extensions). Carry the full
callflow field set (name, `exten`/`exten_number` → `connect.twilio.exten`,
`language` Selection from `_get_language_selection()`, voice, gather config,
`choices`, `ring_users`, voicemail) plus:

| Field | Type | Notes |
|-------|------|-------|
| `gather_action_url` | Char | Computed webhook URL for gather results |

**Key Methods:**

| Method | Description |
|--------|-------------|
| `render()` | Generate TwiML `<Gather>` with `<Say>` prompt |
| `gather_action()` | Webhook: process DTMF/speech input, route to extension |
| `_get_gather_action_url()` | Compute gather action webhook URL |
| `on_call_action()` | Handle call action from gather input |
| `create_extension()` | Create associated `connect.twilio.exten` |
| `_get_language_selection()` | BCP-47 language list — **duplicated** with `connect.freeswitch.callflow`, `connect.telnyx.callflow` and core `connect.user`; changes must be applied to all four (ADR-031/ADR-037) |

`prompt_message` is independent of `gather_input`: `render()` emits it inside
`<Gather>` when input is enabled and as a standalone `<Say>` otherwise. The
call-flow form therefore keeps Prompt Message visible in both modes; Gather
Settings, Invalid Input Message and Choices remain conditional. Gather Settings
and Invalid Input Message share a row, while Prompt Message uses a separate
full-width section (ADR-051).

`connect.twilio.callflow_choice`: `callflow` (required), `choice_digits`
(required), `exten` (`connect.twilio.exten`, required), `speech`.

---

### 10. exten.py - `connect.twilio.exten` (own model, ADR-031)

Extension routing — full standalone model (formerly `connect.exten`).
`number` (required, `UNIQUE` within Twilio), `model`/`res_id` with the computed
`dst` Reference (+inverse) pointing at `connect.user` /
`connect.twilio.callflow` / `connect.twilio.twiml`, `dst_name`, TwiML preview.
The dst-Reference mechanics are **duplicated** with
`connect.freeswitch.exten`; fixes must be applied to both (ADR-031).
Extension uniqueness is per provider — cross-provider uniqueness disappeared by
design.

---

### 11. user_callflow.py - `connect.twilio.user_callflow` + `connect.twilio.user_callflow_call` (own models, ADR-031)

Per-user call delivery steps (SIP/client legs), formerly
`connect.user_callflow`/`connect.user_callflow_call`. Same shape: `user`
(`connect.user`), `prio`, `callflow_type`, `method`; the `_call` model links a
`connect.call` to the step.

The walk is stateful only once the ledger call exists. `connect.settings.
originate_call()` (click-to-call) renders the dialplan *before* the channel
is created, so `connect.user.render()` cannot log the step it used there.
It instead appends `?done_callflows=<ids>` to the `<Dial>` action URL, and
`on_call_action()` folds those ids into `user_callflow_call` as soon as the
call record is available. A `<Dial>` with an action URL makes every later
verb unreachable, so exactly one step is rendered per request.

---

### 12. message_configuration.py - `connect.twilio.message_configuration` (own model, ADR-031)

Incoming-message routing, formerly core `connect.message_configuration`:
`number` (Many2one `connect.twilio.number`, required), `destination` Selection
(`res.partner`), `default_values` (Text holding a **Python dict literal**,
validated by a constraint via `ast.literal_eval` — not JSON). The CRM
extension of this model lives in the auto-installed bridge module
`connect_crm_twilio` (depends on `connect_crm` + `connect_twilio`).

---

### 13. twiml.py - `connect.twilio.twiml` (renamed from `connect.twiml`, 100% Twilio)

TwiML application management. Stores TwiML code or Python code that generates TwiML.

**Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `sid` | Char | Twilio Application SID |
| `old_sid` | Char | Previous SID (for migration) |
| `name` | Char | Application name |
| `description` | Text | |
| `code_type` | Selection | `twiml`, `twipy`, `model_method` |
| `twiml` | Text | Raw TwiML code (Jinja2 template) |
| `twipy` | Text | Python code that generates TwiML |
| `model` | Char | Odoo model name (for model_method type) |
| `method` | Char | Method name to call |
| `voice_url` | Char | Computed |
| `voice_fallback_url` | Char | Computed |
| `voice_status_url` | Char | Computed |
| `exten` | Many2one | `connect.twilio.exten` |
| `exten_number` | Char | Related |

**Methods:**

| Method | Description |
|--------|-------------|
| `create_twilio_app()` | Create Twilio Application via API |
| `update_twilio_app()` | Update Twilio Application webhook URLs |
| `sync()` | Sync applications from Twilio API |
| `render()` | Main render: dispatch to twiml/twipy/model_method |
| `render_twiml()` | Render TwiML via Jinja2 template |
| `render_python()` | Execute Python code (exec) to generate TwiML |
| `_get_twilio_urls()` | Compute webhook URLs |
| `create_extension()` | Create associated `connect.twilio.exten` |
| `create()` | Override: create Twilio app on record creation |
| `write()` | Override: update Twilio app on change |
| `unlink()` | Override: delete Twilio app on removal |

---

### 14. domain.py - `connect.twilio.domain` (renamed from `connect.domain`, 100% Twilio)

Twilio SIP domain management for SIP trunking.

**Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `sid` | Char | Twilio SIP Domain SID |
| `application` | Many2one | `connect.twilio.twiml` |
| `cred_list_sid` | Char | Twilio Credential List SID |
| `subdomain` | Char | SIP subdomain |
| `domain_name` | Char | Computed full domain |
| `edge_domains` | Text | Computed edge-specific domains |
| `friendly_name` | Char | |
| `sip_registration` | Boolean | Allow SIP registration |
| `delete_protection` | Boolean | Prevent accidental deletion |

**Methods:**

| Method | Description |
|--------|-------------|
| `create_twilio_sip_domain()` | Create SIP domain on Twilio |
| `_create_user_credentials_for_domain()` | Create credential list and add users |
| `_import_existing_domain_by_name()` | Import existing Twilio domain |
| `_import_sip_credentials_from_twilio()` | Import existing credentials |
| `create_domain()` | High-level domain creation workflow |
| `update_twilio_domain()` | Push domain config to Twilio |
| `sync()` | Sync SIP domains from Twilio API |
| `route_call()` | Route incoming SIP call to user extension; inbound WhatsApp falls back to `connect.twilio.number` |
| `originate_external_call()` | Originate outbound call via SIP domain |
| `originate_whatsapp_call()` | Originate WhatsApp call via domain |
| `get_domain_app()` | Get or create the domain's TwiML application |

`route_call()` resolves the dialled value to `found_num` and looks it up in
`connect.twilio.exten`. The meaning of `found_num` differs per path: on the SIP
path it is what the softphone dialled (an outbound destination), while for an
inbound WhatsApp call it is one of our own numbers. Because of that, only the
WhatsApp branch falls back to `connect.twilio.number` — searching
`phone_number` and delegating to its `render()` — so a WhatsApp call reaches
the same user or callflow a PSTN call to that number reaches, with no separate
extension. An extension still wins when one exists; the "Whatsapp Extension not
found" prompt remains for a number that matches neither. The SIP path keeps its
old behaviour: falling back there would turn dialling our own number into a
loop back inbound instead of an outbound call. See ADR-057.

---

### 15. whatsapp_sender.py - `connect.whatsapp_sender` (100% Twilio)

Twilio WhatsApp sender/business account management.

**Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `sid` | Char | Twilio Sender SID |
| `number` | Char | WhatsApp phone number |
| `status` | Char | |
| `url` | Char | |
| `offline_reasons` | Text | |
| `number_id` | Many2one | `connect.twilio.number` |
| `profile_name` | Char | Business Name |
| `profile_about` | Char | |
| `profile_vertical` | Char | Business vertical |
| `profile_address` | Char | |
| `profile_description` | Text | |
| `callback_url` | Char | Computed |
| `status_callback_url` | Char | Computed |
| `messaging_limit` | Char | |
| `quality_rating` | Char | |
| `voice_application` | Many2one | `connect.twilio.twiml` |
| `no_sync` | Boolean | Skip during sync |
| `is_default` | Boolean | |

**Methods:**

| Method | Description |
|--------|-------------|
| `sync()` | Sync WhatsApp senders from Twilio messaging API |
| `action_sync()` | UI button wrapper around `sync()` |
| `get_default_sender()` | Return an `ONLINE`, synchronized sender in user preference → global default → fallback order; unavailable preferences/defaults are skipped |
| `send_whatsapp()` | Send WhatsApp message via Twilio API |
| `chatter_post()` | Post WhatsApp message to partner chatter |
| `update_message_status()` | Webhook: update message delivery status |
| `_prepare_vals_from_api()` | Parse Twilio API response into field values |
| `_get_twilio_urls()` | Compute webhook URLs |

---

### 16. message_content_template.py - `connect.message_content_template` (100% Twilio)

Twilio WhatsApp content/message templates. Pre-approved templates for WhatsApp Business API.

---

## Controllers (connect_twilio/controllers/)

### twilio_webhooks.py

All routes under `/twilio/webhook/` with Twilio request signature validation.

| Route | Method | Description |
|-------|--------|-------------|
| `/twilio/webhook/callstatus` | POST | Call status callback → `connect.call.on_call_status()` |
| `/twilio/webhook/callaction` | POST | Call action callback → `connect.call.on_call_action()` |
| `/twilio/webhook/<string:model_name>/call_action/<int:record_id>` | POST | Model-specific `<Dial>` action callback → `model.on_call_action(record_id, kw)`; legacy model names still arriving from stale Twilio-side URLs are remapped via `LEGACY_CALL_ACTION_MODELS` (`connect.callflow` → `connect.twilio.callflow`) |
| `/twilio/webhook/recordingstatus` | POST | Recording status callback → `connect.recording.on_recording_status()` |
| `/twilio/webhook/vm_recordingstatus` | POST | Voicemail recording callback → `connect.call.on_vm_recording_status()` |
| `/twilio/webhook/message` | POST | Incoming SMS/WhatsApp → `connect.message.receive()` |
| `/twilio/webhook/message_status` | POST | Message delivery status → `connect.whatsapp_sender.update_message_status()` |
| `/twilio/webhook/outgoing_callerid` | POST | Caller ID validation status → `connect.twilio.outgoing_callerid.update_status()` |
| `/twilio/webhook/number` | POST | Inbound call to a Twilio number → `connect.twilio.number.route_call()` |
| `/twilio/webhook/twiml/<int:twiml_id>` | POST | TwiML app voice request → `connect.twilio.twiml.render()` |
| `/twilio/webhook/callflow/<int:flow_id>/gather` | POST | Callflow gather result → `connect.twilio.callflow.gather_action()` |
| `/twilio/webhook/domain` | POST | Inbound SIP-domain call → `connect.twilio.domain.route_call()` |

**Signature validation:** All webhook routes validate the `X-Twilio-Signature` header
using `twilio.request_validator.RequestValidator` when `twilio_verify_requests` is enabled
in settings. `check_signature()` takes no arguments and validates against
`request.httprequest.form` — the POST body only. Twilio signs the request URL
(query string included) **plus** the POST parameters, and Odoo merges the query
string into the route kwargs, so validating with those counts a query parameter
twice and no URL carrying one can validate (ADR-059).

---

## Wizards (connect_twilio/wizard/)

### sms_composer.py - inherits `sms.composer` (moved from core, ADR-031)

| Field | Type | Notes |
|-------|------|-------|
| `outgoing_callerid` | Selection | List of available outgoing numbers (raw SQL over the `connect_twilio_number` table) |

**Methods:**

| Method | Description |
|--------|-------------|
| `_list_all_numbers()` | Return available outgoing numbers for selection |
| `_action_send_sms()` | Override: send SMS via `connect.message.send()` (Twilio implementation) |

### whatsapp_composer.py - `connect.whatsapp_composer` (TransientModel)

WhatsApp message sending wizard. Uses `whatsapp_sender.send_whatsapp()` to send messages.

| Field | Type | Notes |
|-------|------|-------|
| `whatsapp_sender_id` | Many2one | `connect.whatsapp_sender` |
| `phone` | Char | Recipient; rendered with `widget="phone"` |
| `body` | Text | |
| `content_template_id` | Many2one | `connect.message_content_template` |
| `content_variables` | Text | Template variables as JSON |

---

## Security

### Groups

Uses core `group_webhook` for webhook access to Twilio-created records.

### Access Rules

| Model | User | Admin | Webhook |
|-------|------|-------|---------|
| `connect.twilio.exten` | Read | Full | Read |
| `connect.twilio.callflow` | Read | Full | Read |
| `connect.twilio.callflow_choice` | Read | Full | Read |
| `connect.twilio.number` | Read | Full | Read |
| `connect.twilio.outgoing_callerid` | Read | Full | Read+Write (validation status callback) |
| `connect.twilio.user_callflow` | Read | Full | - |
| `connect.twilio.user_callflow_call` | Read | Full | - |
| `connect.twilio.message_configuration` | - | Full | - |
| `connect.twilio.twiml` | Read | Full | Read |
| `connect.twilio.domain` | Read | Full | Read |
| `connect.whatsapp_sender` | Read | Full | Read+Write+Create |
| `connect.message_content_template` | Read | Full | - |
| `connect.whatsapp_composer` | Full | Full | - |
| `sms.composer` | Full (extra row for `connect.group_user` on the core wizard) | (Odoo base rules) | - |

`connect.twilio.message_configuration` is admin-only (infrastructure/config
model), mirroring the old core rule.

### Record Rules

- Standard user/admin visibility rules for Twilio-only models.

---

## Data

### data/twiml.xml

Three seed TwiML applications (`connect.twilio.twiml`): **SIP Domain Calls**
(`domain_route_call`), **Reject** (`twiml_reject`) and **Connection Failed**
(`twiml_connection_failed`).

### data/ir_cron.xml

Scheduled job **Fetch Call Prices from Twilio** (`fetch_call_prices`) — batch
price fetching for completed calls, effective only when the `fetch_call_prices`
setting is enabled.

### data/whatsapp_templates.xml

Default WhatsApp content template: `voice_call_request` - used for voice call consent request.

---

## Views

### Inherited/Extended Views (via `inherit_id`)

| File | Inherits | Changes |
|------|----------|---------|
| `views/user_views.xml` | `connect.view_connect_user_form`, `connect.view_connect_user_tree` | Add SIP/Client phone tab, username, domain, edge, whatsapp_sender, application, twilio_exten; list adds sip_enabled/client_enabled columns |
| `views/call_views.xml` | `connect.view_connect_call_form` | Adds a **Twilio** page to the call form: `call_sid`, `price`, `price_unit`, `price_currency`, `is_price_fetched` |

### New Views

| File | Description |
|------|-------------|
| `views/settings_views.xml` | **Standalone** Twilio settings form (credentials, API keys, region/edge, sync, balance, fetch_call_prices) opened via the parametrized `open_settings_form()` — not a notebook page in the core form |
| `views/number_views.xml` | List + form for `connect.twilio.number` (destination routing incl. twiml) |
| `views/exten_views.xml` | List + form for `connect.twilio.exten` (destination reference) |
| `views/callflow_views.xml` | Form for `connect.twilio.callflow` (choices, gather config, ring users) |
| `views/outgoing_callerid_views.xml` | List + form for `connect.twilio.outgoing_callerid` (Validate button, validation_code) |
| `views/message_configuration_views.xml` | List + form for `connect.twilio.message_configuration` |
| `views/message_views.xml` | Menu entry for the core `connect.message` action under the Twilio app |
| `views/twiml_views.xml` | List + form + search for TwiML apps (ACE code editor, extension, code_type) |
| `views/domain_views.xml` | List + form for SIP domains (subdomain, application, edge_domains) |
| `views/whatsapp_sender_views.xml` | List + form for WhatsApp senders (profile, status, sync) |
| `views/message_content_template_views.xml` | List + form + search for WhatsApp templates (approval workflow) |
| `wizard/sms_composer_views.xml` | SMS composer form (moved from core) |
| `wizard/whatsapp_composer_views.xml` | WhatsApp message sending wizard form (sender, recipient with `phone` widget, template, body) |

### Menu Items

`connect_twilio` owns the **Twilio** submenu of the Connect app (ADR-031).
All provider submenus share sequence 50 under `connect.menu_connect_root`,
so they appear after Calls/Users in installation order and before the core
Configuration menu (seq 100).

```
Connect > Twilio (seq 50)
  +-- Numbers (seq 10)
  +-- Extensions (seq 20)
  +-- Call Flows (seq 30)
  +-- Outgoing Caller IDs (seq 40)
  +-- TwiML Apps (seq 50)
  +-- SIP Domains (seq 60)
  +-- Messages (seq 70)
  |   +-- Messages (seq 10, core connect.message action)
  |   +-- WhatsApp Senders (seq 30, admin)
  |   +-- WhatsApp Templates (seq 40, admin)
  |   +-- Message Configuration (admin)
  +-- Configuration (seq 100, admin)
      +-- Settings
```

---

## Frontend (connect_twilio/static/src/)

### Phone Widget (Twilio Voice SDK)

| Path | Description |
|------|-------------|
| `components/phone/` | Phone UI component (dial pad, call controls, status) |
| `js/main.js` | Twilio Device initialization, token refresh, event handlers |
| `js/utils.js` | Utility functions |
| `widgets/phone_field/` | Click-to-call phone field widget |
| `services/` | Active calls service, mail service extensions |

The phone widget uses the Twilio Voice JavaScript SDK (`@twilio/voice-sdk`) to:
- Initialize a Twilio Device with JWT token from `connect.user.get_client_token()`
- Handle incoming calls (ring, accept, reject)
- Make outgoing calls (dial pad, click-to-call from partner form)
- Show active call status (duration, caller info)
- Transfer calls
- Manage call hold/mute
- Start/stop recording for the active call through the core softphone recording RPCs

---

## Dependencies Summary

```
connect_twilio
  depends: ['connect']
  python:  ['twilio']
```

**Note:** `openai` is NOT a dependency of `connect_twilio`. It is a dependency of core
`connect`, where transcription lives.
