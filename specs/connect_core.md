# Connect Core Module Specification

## Module Info

- **Name:** Oduist Connect
- **Technical:** `connect`
- **Version:** 19.0.1.0.0
- **Depends:** `base`, `mail`, `contacts`
- **Python deps:** `phonenumbers`, `jinja2`, `openai` (for transcription - not Twilio-specific)
- **Application:** True
- **License:** LGPL-3

## Overview

The core `connect` module is a technology-agnostic base for telephony integration in Odoo.
It stores call data, messages, recordings, user profiles, and routing configuration without
any dependency on a specific telephony provider. Integration modules (`connect_twilio`,
`connect_freeswitch`, etc.) extend these models via `_inherit` to add provider-specific
fields, webhook handlers, and API calls.

OpenAI transcription and SMS composition live in core because they are not tied to any
specific telephony provider. Any integration module can trigger transcription on a recording
or send an SMS through the abstract `send()` method.

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
| `transcript_provider` | Selection | `openai` |
| `summary_prompt` | Text | GPT prompt for call summaries |
| `register_summary` | Boolean | Default: True - post summary to chatter |
| `instance_uid` | Char | Computed UUID |
| `api_url` | Char | Computed |
| `api_fallback_url` | Char | |
| `web_base_url` | Char | Computed |
| `module_version` | Char | Computed |
| `odoo_version` | Char | Computed |
| `installation_date` | Datetime | Computed |
| `call_duration_limit` | Integer | Computed |
| `customer_code` | Char | |
| `registration_number` | Char | Computed |
| `registration_key` | Char | Computed |
| `is_registered` | Boolean | |
| `i_agree_to_register` | Boolean | |
| `i_agree_to_contact` | Boolean | |
| `i_agree_to_receive` | Boolean | |
| `admin_name` | Char | |
| `admin_phone` | Char | |
| `admin_email` | Char | |
| `company_name` | Char | |
| `company_country` | Many2one | `res.country` |
| `latest_versions` | Html | Readonly |
| `openai_api_key` | Char | Groups: `base.group_erp_manager` |
| `display_openai_api_key` | Char | Masked display field |

**Methods:**

| Method | Description |
|--------|-------------|
| `get_param()` | Singleton parameter access |
| `set_param()` | Singleton parameter write |
| `open_settings_form()` | UI action to open settings |
| `connect_notify(bus)` | Send bus notification |
| `connect_reload_view(bus)` | Send bus reload event |
| `set_defaults()` | Set installation defaults |
| `set_instance_uid()` | Generate UUID for instance |
| `register_instance()` | Register with Oduist API |
| `update_instance_registration()` | Update registration data |
| `prepare_registration_data()` | Build registration payload |
| `update_usage()` | Track usage statistics |
| `make_usage_request()` | HTTP call to usage API |
| `check_api_url()` | Validate API URL reachability |
| `reformat_numbers_button()` | Re-normalize partner phone numbers |
| `action_open_system_parameters()` | UI action |
| `check_latest_versions()` | Version check against API |
| `get_openai_client()` | Create and return OpenAI client instance |

**Notes:**
- `openai_api_key` and `get_openai_client()` live here because transcription is not
  tied to any specific telephony provider. Any integration module can use OpenAI
  for recording transcription.
- `display_openai_api_key` uses protected field masking pattern (shows `****` unless
  the user is in `base.group_erp_manager`).

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
| `transcript` | Text | Computed from recording |
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
| `_get_recording_data()` | Compute recording/transcript/widget fields |
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

**Methods:**

| Method | Description |
|--------|-------------|
| `_get_channel_numbers()` | Generic regex-based number parsing. Handles: phone numbers, whatsapp: prefix stripping, SIP/client URI parsing via `connect.user.get_user_by_uri`. |
| `_get_duration_human()` | Human-readable duration |

---

### 4. message.py - `connect.message`

Order: `create_date DESC`

**Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Computed |
| `from_number` | Char | Required |
| `to_number` | Char | Required |
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
| `action_retry()` | Retry failed message - calls `self.env['connect.message'].send()` |

**Important:** The `send()` method is NOT defined in core. It is abstract and must be
implemented by an integration module (e.g., `connect_twilio` implements it via Twilio API).
`action_retry()` calls `send()`, which will dispatch to whichever integration module
provides the implementation.

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
| `transcript` | Text | |
| `transcription_token` | Char | |
| `transcription_error` | Char | |
| `transcription_price` | Char | |
| `summary` | Html | |
| `list_view_summary` | Html | Computed truncated version |

**Methods:**

| Method | Description |
|--------|-------------|
| `_get_recording_widget()` | HTML audio player with proxy URL |
| `_get_list_view_summary()` | Truncated summary for list views |
| `_get_duration_human()` | Human-readable duration |
| `_sync_summary()` | Constrains: sync summary to call record |
| `get_transcript()` | Trigger transcription workflow |
| `transcribe_recording()` | Call OpenAI Whisper API for speech-to-text |
| `make_summary()` | Call OpenAI GPT-4o for call summary generation |
| `update_transcript()` | Async callback handler for transcript updates |

**Notes:**
- Transcription and summary methods use OpenAI directly (not Twilio), so they belong
  in core. The `openai` Python package is a core dependency.
- `create()` override auto-triggers transcription if `transcript_calls` setting is enabled.
- `transcribe_recording()` downloads the audio from `media_url` (which may be proxied)
  and sends it to OpenAI Whisper.
- `make_summary()` uses the `summary_prompt` from settings with GPT-4o.

---

### 6. user.py - `connect.user`

Rec name: `username`
Order: `username`

**Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Computed from user/username |
| `username` | Char | Required, alphanumeric |
| `user` | Many2one | `res.users` |
| `exten` | Many2one | `connect.exten`, readonly |
| `exten_number` | Char | Related to exten |
| `callflow` | One2many | `connect.user_callflow` |
| `record_calls` | Boolean | Default: True |
| `voicemail_enabled` | Boolean | |
| `voicemail_prompt` | Text | Jinja2 template |
| `outgoing_callerid` | Many2one | `connect.outgoing_callerid` |
| `missed_calls_notify` | Boolean | |
| `greeting_message` | Char | |
| `summary_prompt` | Char | Per-user override |
| `active` | Boolean | Default: True |

**Constraints:**
- `UNIQUE(user)` - one connect.user per res.users
- `UNIQUE(username)` - unique username

**Methods:**

| Method | Description |
|--------|-------------|
| `_get_name()` | Compute name from linked res.users or username |
| `_check_username()` | Constrains: alphanumeric only |
| `manage_group()` | Add/remove security groups on linked res.users |
| `get_user_by_exten_number()` | Lookup connect.user by extension number |
| `get_user_by_uri()` | Lookup connect.user by SIP URI or client identity |
| `create_extension()` | Create associated `connect.exten` record |
| `render_voicemail_prompt()` | Render Jinja2 voicemail template with call context |
| `get_greeting_message()` | Return greeting (override point for integrations) |
| `get_voicemail_prompt()` | Return voicemail prompt (override point) |
| `on_call_action()` | Abstract: handle incoming call action |
| `_manage_channel_callflow()` | CRUD for user callflow entries |
| `_manage_voicemail_enabled()` | Constrains: sync voicemail state |

**Note:** Field is named `user` (not `user_id`) to match the convention from the old module.

---

### 7. user_callflow.py

#### `connect.user_callflow`

| Field | Type | Notes |
|-------|------|-------|
| `user` | Many2one | `connect.user` |
| `prio` | Integer | Priority ordering |
| `callflow_type` | Char | Type of callflow step |
| `method` | Char | Method to invoke |

#### `connect.user_callflow_call`

| Field | Type | Notes |
|-------|------|-------|
| `call` | Many2one | `connect.call` |
| `callflow` | Many2one | `connect.user_callflow` |

---

### 8. endpoint.py - `connect.endpoint`

Keep as-is from current module.

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Required |
| `connect_user_id` | Many2one | `connect.user` |
| `active` | Boolean | |

---

### 9. number.py - `connect.number`

**Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `phone_number` | Char | Required |
| `friendly_name` | Char | |
| `is_default` | Boolean | |
| `destination` | Selection | `user`, `callflow` |
| `callflow` | Many2one | `connect.callflow` |
| `user` | Many2one | `connect.user` |

**Constraints:**
- `UNIQUE(phone_number)`

**Methods:**

| Method | Description |
|--------|-------------|
| `render()` | Route incoming call to the configured destination |
| `route_call()` | Abstract: provider-specific call routing |

**Notes:**
- No `twiml` destination option in core. That is Twilio-specific.
- The `destination` selection is extended by `connect_twilio` to add `twiml`.
- The `twiml` Many2one field also lives only in `connect_twilio`.

---

### 10. outgoing_callerid.py - `connect.outgoing_callerid`

**Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Computed |
| `friendly_name` | Char | Required |
| `number` | Char | Required |
| `status` | Char | |
| `is_default` | Boolean | |
| `callerid_type` | Selection | `outgoing_callerid`, `number` |
| `callerid_users` | One2many | `connect.user` |

**Constraints:**
- `UNIQUE(number)`

**Methods:**

| Method | Description |
|--------|-------------|
| `_get_name()` | Computed: friendly_name + number |
| `_check_number()` | Constrains: must start with `+` |
| `_reset_default()` | Constrains: only one default allowed |
| `_check_default()` | Constrains: validate default selection |

---

### 11. exten.py - `connect.exten`

**Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Computed |
| `number` | Char | Required |
| `model` | Char | Target model name |
| `model_friendly` | Char | Computed human-readable model name |
| `res_id` | Integer | Target record ID |
| `dst` | Reference | Computed with inverse: `connect.user` / `connect.callflow` |
| `dst_name` | Char | Computed display name of destination |
| `twiml` | Text | Computed, readonly - preview of generated response |

**Constraints:**
- `UNIQUE(number)`

**Methods:**

| Method | Description |
|--------|-------------|
| `_get_name()` | Computed name |
| `_get_model_friendly()` | Human-readable model name |
| `_get_dst()` | Compute reference from model/res_id |
| `_set_dst()` | Inverse: write model/res_id from reference |
| `_get_twiml()` | Compute preview of generated telephony response |
| `render()` | Delegate rendering to the destination model |
| `create_extension()` | Factory: create extension for a given destination |
| `create()` | Override: auto-assign number |
| `write()` | Override: handle destination changes |
| `unlink()` | Override: cleanup |
| `copy_data()` | Duplicate extension data |

**Notes:**
- `dst` selection excludes `connect.twiml` in core. The Twilio module adds it.

---

### 12. callflow.py - `connect.callflow`

**Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Required |
| `exten` | Many2one | `connect.exten`, readonly |
| `exten_number` | Char | Related |
| `language` | Char | Default: `en-US` |
| `voice` | Char | Default: `Woman` |
| `gather_input` | Boolean | |
| `gather_input_type` | Selection | `dtmf speech`, `dtmf`, `speech` |
| `gather_timeout` | Integer | Default: 5 |
| `gather_hints` | Char | |
| `prompt_message` | Text | |
| `invalid_input_message` | Text | |
| `gather_digits` | Integer | Default: 1 |
| `choices` | One2many | `connect.callflow_choice` |
| `ring_users` | Many2many | `connect.user` |
| `record_calls` | Boolean | |
| `voicemail_prompt` | Text | |
| `voicemail_enabled` | Boolean | |

**Methods:**

| Method | Description |
|--------|-------------|
| `create_extension()` | Create associated `connect.exten` |
| `get_prompt_message()` | Abstract: return prompt for the caller |
| `get_gather_invalid_input_message()` | Abstract: return invalid input message |
| `get_voicemail_prompt_message()` | Abstract: return voicemail prompt |

**Notes:**
- `render()` is NOT defined in core. The Twilio module adds TwiML rendering.
  The FreeSWITCH module could add dialplan XML rendering.
- Core stores the IVR configuration; integration modules render it into their
  respective protocols.

---

### 13. callflow_choice.py - `connect.callflow_choice`

| Field | Type | Notes |
|-------|------|-------|
| `callflow` | Many2one | `connect.callflow`, required |
| `choice_digits` | Char | Required (DTMF digit(s)) |
| `exten` | Many2one | `connect.exten`, required |
| `speech` | Char | Speech recognition keyword |

---

### 14. debug.py - `connect.debug`

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

### 15. res_partner.py - inherits `res.partner`

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
| `get_partner_by_number()` | Search partner by phone number (uses number_search_operation setting) |
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

### 16. res_users.py - inherits `res.users`

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

### 17. mail.py

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

### 18. message_configuration.py - `connect.message_configuration`

| Field | Type | Notes |
|-------|------|-------|
| `number` | Many2one | `connect.number`, required |
| `destination` | Selection | `res.partner` |
| `default_values` | Text | JSON default field values |

**Methods:**

| Method | Description |
|--------|-------------|
| `_check_default_values()` | Constrains: validate JSON format |

---

### 19. favorite.py - `connect.favorite`

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | |
| `phone_number` | Char | Required |
| `user` | Many2one | `res.users` |
| `partner` | Many2one | `res.partner` |

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
- `_serve_media()` is abstract. It needs authentication credentials from the integration
  module to fetch the actual audio file from the provider. Core provides the routing
  structure; integration modules override with provider-specific auth (e.g., Twilio
  basic auth with account_sid/auth_token).

---

## Wizards (connect/wizard/)

### transfer.py - `connect.transfer_wizard` (TransientModel)

| Field | Type | Notes |
|-------|------|-------|
| `phone_number` | Char | Target number for transfer |

**Methods:**

| Method | Description |
|--------|-------------|
| `action_confirm()` | Execute the transfer |

### sms_composer.py - inherits `sms.composer`

| Field | Type | Notes |
|-------|------|-------|
| `outgoing_callerid` | Selection | List of available outgoing numbers |

**Methods:**

| Method | Description |
|--------|-------------|
| `_list_all_numbers()` | Return available outgoing numbers for selection |
| `_action_send_sms()` | Override: send SMS via `connect.message.send()` |

**Notes:**
- The SMS composer lives in core because it is a UI-level feature that works with any
  integration module.
- `_action_send_sms()` calls `self.env['connect.message'].send()`, which is abstract
  in core. The actual send implementation is provided by whichever integration module
  is installed (e.g., `connect_twilio` implements `send()` via Twilio API).

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
| `connect.user` | Read | Full | - |
| `connect.number` | Read | Full | - |
| `connect.outgoing_callerid` | Read | Full | - |
| `connect.exten` | Read | Full | - |
| `connect.callflow` | Read | Full | - |
| `connect.callflow_choice` | Read | Full | - |
| `connect.user_callflow` | Read | Full | - |
| `connect.user_callflow_call` | Read | Full | - |
| `connect.debug` | Read | Full | Create |
| `connect.settings` | Read | Full | - |
| `connect.endpoint` | Read | Full | - |
| `connect.message_configuration` | Read | Full | - |
| `connect.favorite` | Read+Write | Full | - |

### Record Rules

- Users see only their own `connect.user` records
- Admins see all `connect.user` records
- Users see calls/messages/recordings associated with their `connect.user` or where they
  are the `caller_user`/`answered_user`/`sender_user`

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

---

## Views

All models get list (tree) and form views. Key view details:

| View | Notes |
|------|-------|
| `call_views.xml` | List + form with recording widget, partner button, chatter |
| `channel_views.xml` | List + form |
| `message_views.xml` | List + form with media widget, direction/status icons |
| `recording_views.xml` | List + form with audio player, transcript, summary |
| `user_views.xml` | List + form with callflow, voicemail, extension |
| `number_views.xml` | List + form with destination routing |
| `outgoing_callerid_views.xml` | List + form |
| `exten_views.xml` | List + form with destination reference |
| `callflow_views.xml` | Form with choices, gather config, ring users |
| `debug_views.xml` | List (read-only) |
| `settings_views.xml` | Form with notebook tabs (base tab, registration tab, OpenAI tab) |
| `res_partner_views.xml` | Inherit partner form: add call/message count smart buttons |
| `message_configuration_views.xml` | List + form |
| `favorite_views.xml` | List + form |

### Menu Structure

```
Connect (root)
  +-- Calls (seq 10)
  +-- Messages (seq 20)
  +-- Recordings (seq 30)
  +-- Users (seq 40)
  +-- Numbers (seq 50)
  +-- Caller IDs (seq 60)
  +-- Call Flows (seq 70)
  +-- Extensions (seq 80)
  +-- Configuration
      +-- Settings (seq 10)
      +-- Message Config (seq 20)
      +-- Debug Log (seq 30)
```

---

## Dependencies Summary

```
connect (core)
  depends: ['base', 'mail', 'contacts']
  python:  ['phonenumbers', 'jinja2', 'openai']
```
