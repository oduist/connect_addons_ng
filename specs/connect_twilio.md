# Connect Twilio Module Specification

## Module Info

- **Name:** Oduist Connect Twilio
- **Technical:** `connect_twilio`
- **Version:** 19.0.2.0.0
- **Depends:** `connect`
- **Python deps:** `twilio`
- **Application:** False
- **License:** LGPL-3

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
| `originate_call()` | Override of the core dispatcher: when `_get_originate_provider(user)` is not `'twilio'`, falls through to `super()`; otherwise initiates the outbound call via the Twilio API |
| `get_external_call_route()` | Return TwiML route for external calls |
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

Extends core channel with Twilio SID and webhook-based channel management.

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `sid` | Char | Twilio CallSid for this call leg |

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `on_call_status()` | Twilio webhook: create/update channel records from Twilio params |
| `connect_notify()` | Desktop notification for incoming SIP/Client calls |
| `transfer()` | Channel-level transfer via Twilio API |

---

### 4. message.py - `_inherit = 'connect.message'`

Extends core message with Twilio message handling - implements the abstract `send()` method.

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `message_sid` | Char | Twilio MessageSid (made required in Twilio context) |
| `account_sid` | Char | Twilio Account SID |
| `messaging_service_sid` | Char | Twilio Messaging Service SID |

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `receive()` | Twilio webhook: process incoming SMS/WhatsApp messages |
| `send()` | **Implements abstract:** Send message via Twilio API |
| `client_send()` | Low-level: `client.messages.create()` wrapper |
| `_compute_direction()` | Override: check against Twilio-owned numbers to determine direction |

---

### 5. recording.py - `_inherit = 'connect.recording'`

Extends core recording with Twilio-specific SIDs and webhook handling.

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `sid` | Char | Twilio RecordingSID |
| `call_sid` | Char | Twilio CallSid (channel SID) |

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `on_recording_status()` | Twilio webhook: recording status callback |
| `prepare_data()` | Parse Twilio webhook params into recording field values |
| `sync()` | Sync recordings from Twilio API |
| `create()` | Override: sets sid/call_sid from Twilio params |

**Notes:**
- Transcription methods (`transcribe_recording()`, `make_summary()`, etc.) are NOT here.
  They live in core `connect` because OpenAI transcription is technology-agnostic.
- This module only handles Twilio-specific recording webhook processing and SID tracking.

---

### 6. user.py - `_inherit = 'connect.user'`

Extends core user with Twilio SIP credentials, client tokens, and TwiML rendering.

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `username` | Char | PBX username, `UNIQUE`, alphanumeric. **Not field-level required** (co-installation fix): a constraint on `sip_enabled`/`client_enabled`/`username`/`domain` requires username+domain only when the Twilio SIP or web phone is enabled |
| `originate_provider` | Selection | `selection_add=[('twilio', 'Twilio')]` on the core field |
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
| `whatsapp_sender_id` | Many2one | `connect.whatsapp_sender` |
| `twilio_edge` | Selection | Twilio edge location |

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `_create_sip_account()` | Create SIP credential on Twilio |
| `_import_existing_sip_credential()` | Import existing credential from Twilio |
| `_update_sip_password()` | Update SIP password on Twilio |
| `delete_sip_account()` | Delete SIP credential from Twilio |
| `generate_twilio_password()` | Generate strong random password |
| `render()` | Main TwiML rendering: dispatches to client/sip/voicemail |
| `render_client()` | Generate TwiML `<Dial><Client>` |
| `render_sip()` | Generate TwiML `<Dial><Sip>` |
| `render_voicemail()` | Generate TwiML `<Record>` for voicemail |
| `get_client_token()` | Generate JWT for Twilio Voice SDK |
| `get_client_identity()` | Return SIP identity string |
| `_get_sip_uri()` | Compute SIP URI |
| `_manage_sip_callflow()` | Auto-manage SIP callflow entries |
| `_manage_client_callflow()` | Auto-manage client callflow entries |
| `create()` | Override: auto-create SIP account and extension |
| `write()` | Override: handle SIP credential updates |
| `unlink()` | Override: cleanup SIP account on Twilio |

---

### 7. number.py - `connect.twilio.number` (own model, ADR-031)

Twilio inbound DIDs — full standalone model (formerly a `connect.number`
extension) with Twilio SID, webhook URLs, sync and call routing.

**Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `phone_number` | Char | Required, `UNIQUE` |
| `friendly_name` | Char | |
| `is_default` | Boolean | |
| `destination` | Selection | `user`, `callflow`, `twiml` |
| `callflow` | Many2one | `connect.twilio.callflow` |
| `user` | Many2one | `connect.user` |
| `twiml` | Many2one | `connect.twilio.twiml` |
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
| `status` | Char | |
| `is_default` | Boolean | Only one default allowed |
| `callerid_users` | One2many | `connect.user` via `twilio_outgoing_callerid` |
| `sid` | Char | Twilio OutgoingCallerID SID |
| `validation_code` | Char | Twilio validation code |

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `sync()` | Sync outgoing caller IDs from Twilio API |
| `sync_outgoing_callerid()` | Sync a single caller ID |
| `validate()` | Initiate Twilio phone validation |
| `update_status()` | Webhook: validation status callback |
| `_change_number_friendly_name()` | Constrains: update friendly name on Twilio |
| `create()` | Override: start Twilio validation on create |
| `unlink()` | Override: remove from Twilio on delete |

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
| `_get_language_selection()` | BCP-47 language list — **duplicated** with `connect.freeswitch.callflow`; changes must be applied to both (ADR-031) |

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

---

### 12. message_configuration.py - `connect.twilio.message_configuration` (own model, ADR-031)

Incoming-message routing, formerly core `connect.message_configuration`:
`number` (Many2one `connect.twilio.number`, required), `destination` Selection
(`res.partner`), `default_values` (JSON, validated by constraint). The CRM
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
| `edge_domains` | Char | Computed edge-specific domains |
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
| `route_call()` | Route incoming SIP call to user extension |
| `originate_external_call()` | Originate outbound call via SIP domain |
| `originate_whatsapp_call()` | Originate WhatsApp call via domain |
| `get_domain_app()` | Get or create the domain's TwiML application |

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
| `offline_reasons` | Char | |
| `number_id` | Many2one | `connect.twilio.number` |
| `profile_name` | Char | |
| `profile_about` | Char | |
| `profile_address` | Char | |
| `profile_description` | Text | |
| `profile_emails` | Char | |
| `profile_logo_url` | Char | |
| `profile_websites` | Char | |
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
| `get_default_sender()` | Return the default WhatsApp sender |
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
| `/twilio/webhook/call/status` | POST | Call status callback |
| `/twilio/webhook/call/action` | POST | Call action (gather input) |
| `/twilio/webhook/recording/status` | POST | Recording status callback |
| `/twilio/webhook/voicemail/status` | POST | Voicemail recording callback |
| `/twilio/webhook/message/receive` | POST | Incoming SMS/WhatsApp |
| `/twilio/webhook/message/status` | POST | Message delivery status |
| `/twilio/webhook/callerid/status` | POST | Caller ID validation status |
| `/twilio/webhook/number/<id>/voice` | POST | Inbound call to number |
| `/twilio/webhook/twiml/<id>/voice` | POST | TwiML app voice request |
| `/twilio/webhook/callflow/<id>/gather` | POST | Callflow gather result |

**Signature validation:** All webhook routes validate the `X-Twilio-Signature` header
using `twilio.request_validator.RequestValidator` when `twilio_verify_requests` is enabled
in settings.

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
| `sender_id` | Many2one | `connect.whatsapp_sender` |
| `partner_id` | Many2one | `res.partner` |
| `phone_number` | Char | |
| `body` | Text | |
| `template_id` | Many2one | `connect.message_content_template` |

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

`connect.twilio.message_configuration` is admin-only (infrastructure/config
model), mirroring the old core rule.

### Record Rules

- Standard user/admin visibility rules for Twilio-only models.

---

## Data

### data/whatsapp_templates.xml

Default WhatsApp content template: `voice_call_request` - used for voice call consent request.

---

## Views

### Inherited/Extended Views (via `inherit_id`)

| File | Inherits | Changes |
|------|----------|---------|
| `views/user_views.xml` | `connect.view_connect_user_form`, `connect.view_connect_user_tree` | Add SIP/Client phone tab, username, domain, edge, whatsapp_sender, application, twilio_exten; list adds sip_enabled/client_enabled columns |

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
| `wizard/whatsapp_composer_views.xml` | WhatsApp message sending wizard form (sender, phone, template, body) |

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

---

## Dependencies Summary

```
connect_twilio
  depends: ['connect']
  python:  ['twilio']
```

**Note:** `openai` is NOT a dependency of `connect_twilio`. It is a dependency of core
`connect`, where transcription lives.
