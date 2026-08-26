# Connect Core Module Specification

## Module Info

- **Name:** Oduist Connect
- **Technical:** `connect`
- **Version:** 19.0.4.3.0
- **Depends:** `base`, `mail`, `contacts`, `sms`, `resource`
- **Python deps:** `phonenumbers`, `jinja2`, `httpx` (HTTP client used by settings), `openai` (for transcription - not Twilio-specific), `PyJWT`
- **Application:** True
- **License:** LGPL-3

## Overview

The core `connect` module is a technology-agnostic base for telephony integration in Odoo.
It stores the shared call/message ledger (calls, channels, messages, recordings) and the
PBX user directory (`connect.user`) without any dependency on a specific telephony
provider. Integration modules (`connect_twilio`, `connect_freeswitch`,
`connect_asterisk`) extend these ledger models via `_inherit` to add adapter fields,
webhook handlers, and API calls.

Since ADR-031 core contains **no PBX configuration models**: extensions, call flows,
numbers, endpoints, outgoing caller IDs and message configuration are independent
models owned by the provider modules (`connect.twilio.*`, `connect.freeswitch.*`,
`connect.asterisk.*`). The SMS composer wizard also lives in `connect_twilio`.

OpenAI transcription lives in core because it is not tied to any specific telephony
provider. Any integration module can trigger transcription on a recording, and any
module can implement the abstract `connect.message.send()` contract.

---

## Models (connect/models/)

### 1. settings.py - `connect.settings` (singleton)

Singleton settings model for the Connect module. Uses `get_param()`/`set_param()` pattern
for easy access from other models.

**Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Computed |
| `debug_mode` | Boolean | |
| `number_search_operation` | Selection | `=` or `like` |
| `proxy_recordings` | Boolean | Default: True |
| `transcript_calls` | Boolean | Enable automatic transcription |
| `delete_recording_after_transcription` | Boolean | Default: False; delete successfully processed recording rows after preserving analysis on the linked call |
| `transcript_provider` | Selection | `openai` |
| `openai_summary_model` | Selection | `gpt-5.4-mini` (default) or `gpt-4o` |
| `summary_prompt` | Text | GPT prompt for call summaries |
| `register_summary` | Boolean | Default: True - post summary to chatter |
| `instance_uid` | Char | Computed UUID |
| `api_url` | Char | Computed |
| `api_fallback_url` | Char | |
| `web_base_url` | Char | Computed |
| `call_duration_limit` | Integer | Computed from `ir.config_parameter` |
| `openai_api_key` | Char | Groups: `base.group_erp_manager` |
| `display_openai_api_key` | Char | Masked display field |

**Methods:**

| Method | Description |
|--------|-------------|
| `get_param()` | Singleton parameter access |
| `set_param()` | Singleton parameter write |
| `get_media_auth(media_url)` | Credentials for the media proxy to fetch provider audio; `None` in core, overridden per provider (ADR-060) |
| `open_settings_form(view_xmlid="connect.connect_settings_form", name="General Settings")` | UI action opening the settings singleton through the given form view. Parametrized so each provider module's Settings menu opens the same record through its own standalone view (e.g. `connect_twilio.twilio_settings_form`). |
| `originate_call(number, res_model=None, res_id=None, user=None, **kwargs)` | Click-to-call dispatcher. Resolves the provider via `_get_originate_provider()`; provider modules override and chain via `super()` — each handles the call when its key matches, otherwise falls through. The core base raises a `UserError` when no provider can handle the call. |
| `_get_originate_provider(user=None)` | Resolve the provider key for the user: explicit `connect.user.originate_provider` → the only installed provider (single `selection_add` entry) → `UserError` (none installed, or several installed and no choice made). |
| `_get_message_provider(user=None)` | Same resolution logic for messaging: explicit `connect.user.message_provider` → the only installed messaging provider → `UserError`. Used by provider overrides of `connect.message.send()`. |
| `connect_notify(bus)` | Send bus notification |
| `connect_reload_view(bus)` | Send bus reload event |
| `set_defaults()` | Set installation defaults |
| `check_api_url()` | Validate API URL format |
| `reformat_numbers_button()` | Re-normalize partner phone numbers |
| `action_open_system_parameters()` | UI action |
| `get_openai_client()` | Create and return OpenAI client instance |

**Notes:**
- `openai_api_key` and `get_openai_client()` live here because transcription is not
  tied to any specific telephony provider. Any integration module can use OpenAI
  for recording transcription.
- `display_openai_api_key` uses protected field masking pattern (shows `****` unless
  the user is in `base.group_erp_manager`).
- `connect.settings` stays **one model** even with several providers installed:
  provider fields all live on the singleton, but each provider ships its own
  standalone settings form view + menu (no notebook-page injection into the core
  form since ADR-031).

---

### 2. call.py - `connect.call`

Inherits: `mail.thread`, `mail.activity.mixin`
Order: `id desc`

**Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Computed |
| `channels` | One2many | `connect.channel` |
| `recording` | Many2one | `connect.recording`, computed |
| `transcript` | Text | Stored durable call transcript |
| `recording_widget` | Html | Computed audio player |
| `recording_icon` | Html | Computed |
| `summary` | Html | |
| `called` | Char | |
| `caller` | Char | |
| `parent_call` | Many2one | `connect.call` (self-referential) |
| `partner` | Many2one | `res.partner` |
| `partner_img` | Binary | Related to partner |
| `direction` | Char | Index: True (incoming/outgoing/internal) |
| `call_type` | Selection | `phone`, `whatsapp` |
| `status` | Char | |
| `duration` | Integer | Seconds |
| `duration_minutes` | Float | Computed |
| `duration_human` | Char | Computed (e.g. "2m 30s") |
| `caller_pbx_user` | Many2one | `connect.user` |
| `answered_pbx_user` | Many2one | `connect.user` |
| `called_pbx_users` | Many2many | `connect.user` |
| `caller_user` | Many2one | `res.users` |
| `caller_user_img` | Binary | Related |
| `called_users` | Many2many | `res.users` |
| `answered_user` | Many2one | `res.users` |
| `answered_user_img` | Binary | Related |
| `scheduled_datetime` | Datetime | |
| `voicemail_url` | Char | |
| `voicemail_duration` | Integer | |
| `voicemail_icon` | Html | Computed |
| `voicemail_widget` | Html | Computed |
| `ref` | Reference | Computed - linked business record |
| `has_error` | Boolean | |
| `error_code` | Char | |
| `error_message` | Text | |

**Methods:**

| Method | Description |
|--------|-------------|
| `_get_name()` | Compute display name from caller/called |
| `_get_ref()` | Compute reference to linked record |
| `_get_recording_data()` | Compute recording/widget fields |
| `_get_voicemail_widget()` | HTML audio player for voicemail |
| `_get_voicemail_icon()` | Voicemail indicator icon |
| `_get_duration_human()` | Human-readable duration string |
| `register_call()` | Post call summary to partner chatter |
| `register_call_post_message()` | Helper for chatter message creation |
| `register_summary_to_rec()` | Write summary to linked record |
| `register_partner_call_summary()` | Constrains: auto-register on partner change |
| `create_partner_button()` | UI: create partner from call number |
| `transfer_button()` | UI: open transfer wizard |
| `redial()` | Re-initiate call (calls originate on settings) |
| `get_widget_calls()` | Return data for phone widget |
| `get_widget_fields()` | Return field list for phone widget |
| `on_call_action()` | Generic call action handler (abstract) |

---

### 3. channel.py - `connect.channel`

Inherits: `mail.thread`
Order: `id desc`

**Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `call` | Many2one | `connect.call` |
| `parent_channel` | Many2one | `connect.channel` (self-referential) |
| `parent_sid` | Char | |
| `partner` | Many2one | `res.partner` |
| `called` | Char | |
| `to` | Char | |
| `technical_direction` | Char | inbound/outbound-api/outbound-dial |
| `status` | Char | |
| `duration` | Integer | Seconds |
| `duration_minutes` | Float | |
| `duration_billing` | Integer | |
| `duration_human` | Char | Computed |
| `caller` | Char | |
| `call_type` | Selection | `phone`, `whatsapp` |
| `caller_pbx_user` | Many2one | `connect.user` |
| `called_pbx_user` | Many2one | `connect.user` |
| `caller_user` | Many2one | `res.users` |
| `called_user` | Many2one | `res.users` |
| `caller_number` | Char | Computed, stored |
| `called_number` | Char | Computed, stored |
| `recording_state` | Selection | Runtime softphone recording control state: `off`, `on`, `starting`, `stopping`, `error` |
| `recording_control_ref` | Char | Provider recording reference used by runtime controls |
| `recording_control_path` | Char | Provider recording path/URL used by runtime controls |
| `recording_control_error` | Char | Last runtime recording control error |

**Methods:**

| Method | Description |
|--------|-------------|
| `_get_channel_numbers()` | Generic regex-based number parsing. Handles phone numbers, `whatsapp:` prefix stripping, and SIP/client URIs with or without a URI scheme via `connect.user.get_user_by_uri` (ADR-051). |
| `_get_duration_human()` | Human-readable duration |
| `get_softphone_recording_state(payload)` | Provider-dispatched RPC returning runtime recording support/state for the active softphone call. |
| `start_softphone_recording(payload)` | Provider-dispatched RPC to start recording the active softphone call. |
| `stop_softphone_recording(payload)` | Provider-dispatched RPC to stop recording the active softphone call. |
| `_softphone_recording_channel(payload)` | Resolve a provider channel SID and verify the requester is a participant or Connect admin. |
| `_check_softphone_recording_active()` | Reject runtime controls for completed/busy/failed/no-answer/canceled channels. |

---

### 4. message.py - `connect.message`

Order: `create_date DESC`

**Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Computed |
| `from_number` | Char | Required; `phone` widget in the message form |
| `to_number` | Char | Required; `phone` widget in the message form |
| `body` | Text | |
| `num_media` | Integer | |
| `message_type` | Char | sms/WhatsApp/mms |
| `status` | Char | Default: `draft` |
| `direction` | Selection | Computed, stored (incoming/outgoing) |
| `direction_display` | Html | Computed icon |
| `status_display` | Html | Computed icon |
| `sender_user` | Many2one | `res.users` |
| `sender_user_img` | Binary | Related |
| `partner` | Many2one | `res.partner` |
| `partner_img` | Binary | Related |
| `from_city` | Char | |
| `from_state` | Char | |
| `from_zip` | Char | |
| `from_country` | Char | |
| `has_error` | Boolean | |
| `error_code` | Char | |
| `error_message` | Char | |
| `res_model` | Char | |
| `res_id` | Integer | |
| `ref` | Reference | Computed, stored |
| `parent_message` | Many2one | `connect.message` (self-referential) |
| `media_url` | Char | |
| `media_content_type` | Char | |
| `media_widget` | Html | Computed |

**Methods:**

| Method | Description |
|--------|-------------|
| `_compute_name()` | Display name from numbers |
| `_compute_direction()` | Abstract - determines direction by checking sender_user/status. Integration modules override to check provider-specific number ownership. |
| `_compute_direction_display()` | Arrow icon based on direction |
| `_compute_status_display()` | Status badge icon |
| `_compute_ref()` | Reference to linked business record |
| `_format_phone_number()` | Static method for phone formatting |
| `_get_media_widget()` | HTML for media display (image/audio) |
| `_reference_models()` | Dynamic selection of reference models |
| `get_receive_message_values()` | Parse incoming webhook params into field values |
| `send(recipient, body, res_id=None, res_model=None, outgoing_callerid=None, **kwargs)` | Messaging dispatcher terminal (mirror of `originate_call()`). Provider modules override: each handles the message when `connect.settings._get_message_provider()` returns its key, otherwise falls through to `super()`. The core base raises a `UserError` when no provider can handle the message. |
| `action_retry()` | Retry failed message - calls `self.env['connect.message'].send()` |

**Important:** The core `send()` only dispatches — the actual transport is
implemented by messaging provider modules (`connect_twilio`, `connect_bird`).
The provider is resolved per user via `connect.user.message_provider` with a
single-installed-provider fallback (see `_get_message_provider()`).

---

### 5. recording.py - `connect.recording`

Inherits: `mail.thread`, `mail.activity.mixin`
Order: `id desc`

**Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `call` | Many2one | `connect.call` |
| `channel` | Many2one | `connect.channel` |
| `partner` | Many2one | `res.partner` |
| `caller_user` | Many2one | Related via `call.caller_user` |
| `called_user` | Many2one | `res.users` |
| `users` | Many2many | Computed union of recording and linked-call Odoo users |
| `caller_number` | Char | |
| `called_number` | Char | |
| `media_url` | Char | |
| `price` | Char | |
| `price_unit` | Char | |
| `source` | Char | |
| `duration` | Integer | |
| `duration_human` | Char | Computed |
| `start_time` | Datetime | |
| `status` | Char | |
| `recording_widget` | Html | Computed audio player |
| `transcript` | Text | Provider-compatible copy synchronized to `call.transcript` |
| `transcription_token` | Char | |
| `transcription_error` | Char | |
| `transcription_price` | Char | Estimated Whisper cost in USD, stored with up to six decimal places |
| `transcription_pending` | Boolean | Work-queue flag; set on create when `transcript_calls` is on, cleared after manual, callback, or cron processing |
| `summary` | Html | Provider-compatible copy synchronized to `call.summary` |
| `list_view_summary` | Html | Computed truncated version |

**Methods:**

| Method | Description |
|--------|-------------|
| `_get_recording_widget()` | HTML audio player with proxy URL |
| `_compute_users()` | Combine caller, called, and answered Odoo users for list display |
| `_get_list_view_summary()` | Truncated summary for list views |
| `_get_duration_human()` | Human-readable duration |
| `_sync_analysis_to_call()` | Constrains: sync transcript and summary to the call ledger |
| `unlink()` | Preserve the latest recording analysis on its call before deletion |
| `_delete_after_successful_transcription()` | Delete a successfully processed linked recording when automatic deletion is enabled |
| `_format_transcription_price()` | Normalize estimated or callback-provided prices without losing sub-cent values |
| `_get_transcription_price()` | Calculate the Whisper estimate from OpenAI usage seconds or response duration |
| `get_transcript()` | Trigger transcription workflow |
| `transcribe_recording()` | Call OpenAI Whisper API for speech-to-text |
| `make_summary()` | Call the configured OpenAI model for call summary generation |
| `update_transcript()` | Async callback handler for transcript updates |
| `_cron_transcribe_recordings()` | Cron: transcribe `transcription_pending` recordings out of the request path (replaces the old inline transcription + `cr.commit()` in `create()`) |

**Crons:** `cron_transcribe_recordings` (every 2 min) runs
`_cron_transcribe_recordings()`. Transcription is asynchronous: `create()`
only flags the recording (`transcription_pending`) so the provider webhook
that created it returns immediately and the request transaction stays
atomic. A completed manual or callback-driven transcription clears the same
flag. The cron also clears stale pending flags on recordings that already have
a transcript without sending the audio to OpenAI again (ADR-050). When
`delete_recording_after_transcription` is enabled, successful processing stores
the transcript and summary on the linked call before deleting the recording
row. Failed and unlinked recordings are retained (ADR-050).

**Notes:**
- Transcription and summary methods use OpenAI directly (not Twilio), so they belong
  in core. The `openai` Python package is a core dependency.
- `create()` override auto-triggers transcription if `transcript_calls` setting is enabled.
- A transcription attempt clears `transcription_pending` after success or a
  stored error. This preserves the queue's single-attempt behavior and prevents
  duplicate OpenAI requests after a manual transcription.
- `connect.call.transcript` and `connect.call.summary` are the durable analysis
  fields. Recording values remain compatible with provider adapters and are
  synchronized from the latest analyzed recording whenever their values or call
  link changes.
- Automatic deletion removes the Odoo recording row and Odoo-managed attachment;
  it does not change retention in the telephony provider's storage.
- `transcribe_recording()` prefers the stored `recording_attachment` bytes
  (providers whose downloads require API auth store the file on the record,
  e.g. connect_infobip — ADR-036) and only falls back to downloading
  `media_url` (which may be proxied) before sending the audio to OpenAI
  Whisper. `get_transcript()` accepts either source.
- Direct Whisper transcription stores an estimated USD price from OpenAI usage
  seconds (or response duration) at the published USD 0.006/minute rate
  (ADR-050). Callback-provided prices use the same six-decimal precision
  instead of cent rounding.
- `make_summary()` uses the `summary_prompt` and `openai_summary_model` from
  settings. `OPENAI_COMPLETION_MODEL` remains a deployment-level override.

---

### 6. user.py - `connect.user`

Rec name: `name`
Order: `name`

Slimmed by ADR-031: the PBX plumbing (`exten`, `exten_number`,
`outgoing_callerid`, `endpoint_ids`, `callflow`) moved to the provider modules,
which contribute their own fields via `_inherit` (`twilio_exten`,
`freeswitch_exten`, `asterisk_exten_number`, per-provider caller-ID and endpoint
links).

**Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Computed (stored) from `user.name` |
| `user` | Many2one | `res.users`, Required, `domain=[('share','=',False)]` |
| `record_calls` | Boolean | Default: True |
| `voicemail_enabled` | Boolean | |
| `voicemail_prompt` | Text | Jinja2 template |
| `missed_calls_notify` | Boolean | |
| `greeting_message` | Char | |
| `language` | Selection | BCP-47 TTS language for the user's prompts. Default `en-US`. List from `_get_language_selection()` — deliberate 4th copy of the provider callflow lists (ADR-031/ADR-037) |
| `voice` | Char | Provider-specific TTS voice name; empty = provider default (`Woman` on Twilio, `Polly.Joanna` on Telnyx) |
| `summary_prompt` | Char | Per-user override |
| `active` | Boolean | Default: True |
| `originate_provider` | Selection | Base selection is empty; each provider module `selection_add`s its key (`twilio`, `freeswitch`, `asterisk`). Chooses which provider handles click-to-call for this user; may stay empty when only one provider is installed. |
| `message_provider` | Selection | Base selection is empty; messaging provider modules `selection_add` their key (`twilio`, `bird`). Chooses which provider handles `connect.message.send()` for this user; may stay empty when only one messaging provider is installed. |

**Constraints:**
- `UNIQUE(user)` - one connect.user per res.users

**Methods:**

| Method | Description |
|--------|-------------|
| `_get_name()` | Compute name from linked res.users |
| `_pbx_number_fields()` | Provider hook (`@api.model`): names of Char fields on connect.user holding a provider extension number. Returns `[]` in core; provider modules append their field (`twilio_exten_number`, `freeswitch_exten_number`, `asterisk_exten_number`). |
| `get_pbx_number()` | First non-empty provider extension number of this user (iterates `_pbx_number_fields()`). Used e.g. by `connect.channel._get_channel_numbers()`. |
| `get_user_by_exten_number()` | Lookup connect.user by extension number; searches across all `_pbx_number_fields()`, so it works with any combination of installed providers. |
| `get_user_by_uri()` | No-op in core (returns empty recordset). Integration modules override to lookup connect.user by SIP URI or client identity. |
| `manage_group()` | Add/remove security groups on linked res.users |
| `create()` / `write()` / `unlink()` | Group management side effects |

**Note:** Field is named `user` (not `user_id`) to match the convention from the old module.

**Moved models (ADR-031):** `connect.exten`, `connect.callflow` (+`_choice`),
`connect.number`, `connect.endpoint`, `connect.outgoing_callerid`,
`connect.user_callflow` (+`_call`) and `connect.message_configuration` no longer
exist in core. See `specs/connect_twilio.md`, `specs/connect_freeswitch.md` and
`specs/connect_asterisk.md` for their per-provider successors. The
`connect` 19.0.4.0.0 pre-migration archives the old tables as `_*_legacy`.

---

### 7. debug.py - `connect.debug`

Order: `id desc`

| Field | Type | Notes |
|-------|------|-------|
| `model` | Char | Source model name |
| `message` | Text | Debug log content |

**Methods:**

| Method | Description |
|--------|-------------|
| `vacuum(hours=24)` | Cron job: delete debug entries older than 24 hours |

---

### 8. res_partner.py - inherits `res.partner`

**Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `connect_calls_count` | Integer | Computed |
| `connect_messages_count` | Integer | Computed |
| `connect_recorded_calls` | One2many | `connect.recording` |
| `connect_user` | Many2one | Computed |

**Methods:**

| Method | Description |
|--------|-------------|
| `create_record_from_message()` | Create partner from incoming message data |
| `get_partner_by_number()` | Search partner by phone number via `phone_mobile_search`. Falls back to an E.164-normalized lookup (country from the main company) if the literal search returns nothing, so caller IDs delivered in local format still match partners stored in E.164 and vice versa. |
| `_get_connect_calls_count()` | Compute call count |
| `_get_connect_messages_count()` | Compute message count |
| `_normalize_phone()` | Normalize phone number format |
| `_get_country()` | Detect country from phone number |
| `_phone_format()` | Override Odoo's phone formatting |
| `api_get_partner()` | API endpoint for partner lookup by number |

**Utility functions (module-level):**

| Function | Description |
|----------|-------------|
| `strip_number()` | Remove formatting from phone number |
| `format_number()` | Format phone number for display |

---

### 9. res_users.py - inherits `res.users`

**Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `connect_user` | Many2one | Computed |
| `pin_code` | Char | Auto-generated on create |

**Constraints:**
- `UNIQUE(pin_code)`

**Methods:**

| Method | Description |
|--------|-------------|
| `create()` | Override: auto-generate pin_code |
| `_get_connect_user()` | Compute linked connect.user |
| `connect_notify()` | Send bus notification to user |

---

### 10. mail.py

#### Inherits `mail.message`

| Field | Type | Notes |
|-------|------|-------|
| `connect_message` | Many2one | `connect.message` |
| `message_type` | Selection | `selection_add`: WhatsApp |

**Methods:**

| Method | Description |
|--------|-------------|
| `get_message_numbers()` | Extract phone numbers from message |

#### Inherits `mail.notification`

| Field | Type | Notes |
|-------|------|-------|
| `notification_type` | Selection | `selection_add`: WhatsApp |

---

### 11. favorite.py - `connect.favorite`

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | |
| `phone_number` | Char | Required |
| `user` | Many2one | `res.users` |
| `partner` | Many2one | `res.partner` |

### 12. schedule.py - working schedules (issue #57, ADR-037)

Provider-agnostic working-hours engine on top of `resource.calendar`.
Provider modules attach a schedule to their number models and query it per
call; core owns the evaluation, the availability slots and the UI.

**`connect.schedule`**

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Required |
| `calendar_id` | Many2one | `resource.calendar`, required, restrict; global leaves act as public holidays |
| `tz` | Selection | Related `calendar_id.tz` |
| `special_day_ids` | Many2many | `connect.schedule.special_day` |
| `holiday_ids` | One2many | Related `calendar_id.global_leave_ids`, editable |
| `slot_ids` | One2many | `connect.schedule.slot` |
| `preview_html` | Html | Computed 14-day availability table |

Methods:
- `get_status(at_dt=None)` — availability at a naive-UTC moment. Evaluation
  order: special working days for the local date (they fully define the day
  and can extend hours) → global leaves (closed, optional `prompt_message`)
  → weekly attendances (`_attendance_intervals_batch`/`_leave_intervals_batch`,
  two-week calendars supported). Returns `available`, `source`
  (`special`/`holiday`/`schedule`), `label`, `prompt_message`, `until`,
  `next_open` (naive UTC).
- `get_day_data(date_start, days)` — per-day effective windows plus the raw
  attendance/leave/special layers (feeds the preview, the slots and the
  website widgets).
- `generate_slots()` / `_cron_generate_slots()` — materialize
  `connect.schedule.slot` over a rolling horizon
  (`connect.schedule_slot_horizon_days` system parameter, default 60).
  Regenerated by a daily cron and on any write to schedules, special days or
  leaves.

**`connect.schedule.special_day`** — `name`, `date`, `work_from`/`work_to`
(floats, `from < to` enforced; full-day closures are leaves, not special
days), M2M `schedule_ids`. Constraint: windows of special days sharing a
schedule must not overlap on the same date; several non-overlapping windows
per date are allowed.

**`connect.schedule.slot`** — derived calendar events: `schedule_id`,
`name`, `start`/`stop`, `allday`, `slot_type`
(`available`/`schedule`/`holiday`/`special`/`closed`). Rendered by the
first `<calendar>` view in the product (Connect → Availability).

**resource_calendar_leaves.py** — `_inherit = 'resource.calendar.leaves'`:
adds `prompt_message` (Text, played to callers during the leave) and slot
regeneration hooks.

---

## Controllers (connect/controllers/)

### main.py

| Route | Method | Auth | Description |
|-------|--------|------|-------------|
| `/connect/transcript/<id>` | POST | - | Receive transcript callback |
| `/connect/recording/<id>` | GET | user | Serve proxied recording audio |
| `/connect/voicemail/<id>` | GET | user | Serve proxied voicemail audio |
| `/connect/<uid>/` | GET | - | Health check endpoint |

**Notes:**
- `_serve_media()` fetches the provider's audio and streams it to the browser. It takes
  its credentials from `connect.settings.get_media_auth(media_url)`, which core answers
  with `None` and provider modules override (e.g. `connect_twilio` returns
  `(account_sid, auth_token)` for Twilio hosts only). A failed fetch answers `502` and
  logs the upstream status: the audio element itself shows nothing but a 0-second
  recording, so the log is the only place the cause can appear (ADR-060).

---

## Wizards (connect/wizard/)

### transfer.py - `connect.transfer_wizard` (TransientModel)

| Field | Type | Notes |
|-------|------|-------|
| `phone_number` | Char | Target number for transfer; `phone` widget in the wizard |

**Methods:**

| Method | Description |
|--------|-------------|
| `action_confirm()` | Execute the transfer |

**Note:** The SMS composer (`sms.composer` inherit) moved to `connect_twilio`
(ADR-031) — its number list is raw SQL over the Twilio number table. Core only
keeps the abstract `connect.message.send()` contract.

---

## Security

### Groups

| XML ID | Name | Description |
|--------|------|-------------|
| `group_user` | Connect User | Basic access to calls, messages, recordings |
| `group_admin` | Connect Admin | Full CRUD on all models |
| `group_webhook` | Connect Webhook | Create+read access for webhook-created records |

### Access Rules

All models get access rules for the three groups:

| Model | User | Admin | Webhook |
|-------|------|-------|---------|
| `connect.call` | Read | Full | Create+Read |
| `connect.channel` | Read | Full | Create+Read |
| `connect.message` | Read | Full | Create+Read |
| `connect.recording` | Read | Full | Create+Read |
| `connect.user` | Read | Full | Read |
| `connect.debug` | - | Full | Create |
| `connect.settings` | - | Full | - |
| `connect.favorite` | Read+Write | Full | - |
| `connect.transfer_wizard` | Full | Full | - |
| `connect.schedule` | Read | Full | Read |
| `connect.schedule.special_day` | Read | Full | Read |
| `connect.schedule.slot` | Read | Full | - |
| `resource.calendar` (+attendance, +leaves) | Read | Full | - |

Access rules for the PBX configuration models live in the provider modules
next to the models themselves (ADR-031).

`connect.settings` and `connect.debug` are
**admin-only** — `group_user` has no model access. End-user features still need
configuration values, so `connect.settings.get_param()` sudo-finds the singleton
and returns the value without requiring the caller to hold model access; it only
blocks parameters whose field carries a `groups=` restriction (the secrets, e.g.
`openai_api_key`, Twilio `auth_token`, `firewall_service_token`) for non-members,
so a plain user cannot read secrets via `get_param` over RPC. `set_param` stays
non-sudo (configuration writes remain manager-only). The `debug()` helper writes
`connect.debug` via sudo, so logging from user-triggered code keeps working.

### Record Rules

- Users see only their own `connect.user` records
- Admins see all `connect.user` records
- Users see calls/messages/recordings associated with their `connect.user` or where they
  are the `caller_user`/`answered_user`/`sender_user`
- Endpoint record rules (own-device self-management) moved to the provider
  modules together with the endpoint models (`connect.freeswitch.endpoint`,
  `connect.asterisk.endpoint`).

---

## Data

### data/res_users.xml

- `connect.user_connect_webhook` - Special res.users record for webhook processing.
  This user is used by integration modules when creating records from webhook callbacks.

### data/data.xml

- Default `connect.settings` singleton record
- Instance UID initialization

### data/ir_cron.xml

| Cron | Interval | Description |
|------|----------|-------------|
| Debug vacuum | Daily | Delete debug entries older than 24 hours |
| Usage tracking | Daily | Report usage statistics to API |
| Schedule slots | Daily | Regenerate working-schedule availability slots over the rolling horizon |

---

## Views

All models get list (tree) and form views. Key view details:

| View | Notes |
|------|-------|
| `call_views.xml` | Plain caller/called values in lists; form phone widgets, recording widget, durable transcript/summary, partner button, chatter |
| `channel_views.xml` | Plain caller/called values in the list; form phone widgets for caller/called and computed numbers (admin menu entry) |
| `message_views.xml` | Plain from/to values in the list; form phone widgets, media widget, direction/status icons (menu entry lives in connect_twilio) |
| `recording_views.xml` | Plain caller/called values in the list; form phone widgets, audio player, transcript, summary, and optional Partner and Users list columns |
| `user_views.xml` | List + form with voicemail, summary prompt, originate provider |
| `debug_views.xml` | List (read-only) |
| `settings.xml` | Core settings form (general, registration, transcription/OpenAI). Provider settings forms live in their own modules and open the same singleton via the parametrized `open_settings_form()`. |
| `res_partner_views.xml` | Inherit partner form: add call/message count smart buttons |
| `favorite_views.xml` | List + form |
| `license.xml` | License form + menu |

### Menu Structure

**Connect** is the single top-level app. Core carries the shared ledger and
configuration; each provider module plugs its own submenu (**Twilio**,
**FreeSWITCH**, **Asterisk**) under `menu_connect_root` at sequence 50, so
providers appear after Calls/Users in installation order and Configuration
(seq 100) always stays last — see `specs/architecture.md`.

```
Connect (root, seq 10)
  +-- Calls (seq 10)
  |   +-- Calls (seq 10)
  |   +-- Recordings (seq 30)
  |   +-- Channels (admin)
  +-- Users (seq 20)
  +-- Availability (seq 25, slot calendar, group_user)
  +-- <provider submenus> (seq 50, installation order)
  +-- Configuration (seq 100)
      +-- Settings (admin)
      +-- Debug Log (admin)
      +-- Working Schedules (admin, seq 40)
      +-- Special Working Days (admin, seq 41)
      +-- Working Times (admin, seq 42, resource.calendar)
      +-- License (admin)
```

---

## Frontend (connect/static/src/)

Core owns the provider-agnostic phone-widget pieces that read the shared
ledger, so they are defined once instead of being copy-pasted per provider
(`web.assets_backend`):

- `components/license_banner/` — license banner systray item.
- `components/calls/` — shared **Calls history tab** (`Calls` / `CallDetail`,
  templates `connect.calls` / `connect.call_detail`). Provider phone panels
  import it (`import {Calls} from "@connect/components/calls/calls"`) and mount
  it as a child; it reads `connect.call.get_widget_calls` and `connect.favorite`
  and triggers `busPhoneMakeCall` on the provider bus for click-to-call.
- `services/active_calls/` — shared **active-calls systray widget**
  (`ConnectActiveCallsTray` + `ConnectActiveCallsPopup`, service
  `connect_active_calls`). Registered **once**, gated on
  `connect.group_user`; clicking the `fa-server` "Toggle Calls" tray icon shows
  in-progress calls (`connect.call.get_widget_calls`, domain
  `status = in-progress`). Previously duplicated in each of connect_twilio /
  connect_telnyx / connect_infobip.

The provider-specific WebRTC dialer (its own systray icon + `Phone` main
component per SDK) stays in each provider module and is out of scope for this
sharing.

---

## Dependencies Summary

```
connect (core)
  depends: ['base', 'mail', 'contacts', 'sms', 'resource']
  python:  ['phonenumbers', 'jinja2', 'httpx', 'openai', 'PyJWT']
```
