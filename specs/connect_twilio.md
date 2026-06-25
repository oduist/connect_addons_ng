# Connect Twilio Module Specification

## Module Info

- **Name:** Oduist Connect Twilio
- **Technical:** `connect_twilio`
- **Version:** 19.0.1.0.0
- **Depends:** `connect`
- **Python deps:** `twilio`
- **Application:** False
- **License:** LGPL-3

## Overview

The `connect_twilio` module extends the core `connect` module with Twilio-specific
functionality. All models use `_inherit` to add Twilio fields and methods to the
core models. It also introduces three new models that are 100% Twilio-specific:
`connect.twiml`, `connect.domain`, and `connect.whatsapp_sender`.

This module handles: Twilio REST API client, webhook handlers for calls/messages/recordings,
TwiML generation, SIP domain management, WhatsApp integration, Twilio Voice SDK (frontend),
and Twilio number/callerID synchronization.

OpenAI transcription is NOT in this module - it lives in core `connect` because it is
technology-agnostic. The SMS composer also lives in core, with this module implementing
the abstract `send()` method.

---

## Models (connect_twilio/models/) - all use _inherit unless noted

### 1. settings.py - `_inherit = 'connect.settings'`

Extends core settings with Twilio API credentials, client management, and sync.

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `account_sid` | Char | Twilio Account SID |
| `auth_token` | Char | Groups: `base.group_erp_manager` |
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
| `_originate_call()` | Click-to-call: initiate outbound call via Twilio API (dispatched from the `connect.provider` façade) |
| `compute_sip_uri()` | Resolve the SIP URI for the current user |
| `get_external_call_route()` | Return TwiML route for external calls |
| `get_balance()` | Fetch account balance from Twilio API |
| `_reset_edge()` | Onchange: reset `twilio_edge` when `twilio_region` changes |
| `write()` | Override: handle protected field masking for `display_auth_token` and `display_twilio_api_secret` |

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
| `sid` | Char | Twilio SIP credential SID |
| `password` | Char | SIP password, groups restricted |
| `domain` | Many2one | `connect.domain` |
| `sip_enabled` | Boolean | |
| `sip_priority` | Selection | `1` or `2` |
| `sip_ring_timeout` | Integer | Seconds |
| `client_enabled` | Boolean | Default: True |
| `client_priority` | Selection | `1` or `2` |
| `client_ring_timeout` | Integer | Seconds |
| `uri` | Char | Computed: `user@domain` |
| `connect_uri` | Char | Computed: with edge prefix |
| `application` | Many2one | `connect.twiml` |
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

### 7. number.py - `_inherit = 'connect.number'`

Extends core number with Twilio SID, webhook URLs, and sync.

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `sid` | Char | Twilio Phone Number SID |
| `voice_url` | Char | Computed webhook URL |
| `voice_fallback_url` | Char | Computed |
| `voice_status_url` | Char | Computed |
| `message_url` | Char | Computed |
| `message_fallback_url` | Char | Computed |
| `twiml` | Many2one | `connect.twiml` |

**Extends destination selection:** Adds `twiml` option to the `destination` field.

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `sync()` | Sync phone numbers from Twilio API |
| `update_twilio_number()` | Push webhook configuration to Twilio |
| `_get_twilio_urls()` | Compute webhook URLs for this number |
| `write()` | Override: push changes to Twilio on save |
| `route_call()` | Override: Twilio-specific call routing (TwiML response) |

---

### 8. outgoing_callerid.py - `_inherit = 'connect.outgoing_callerid'`

Extends core caller ID with Twilio validation and sync.

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
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

### 9. callflow.py - `_inherit = 'connect.callflow'`

Extends core callflow with TwiML Gather rendering and webhook handling.

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `gather_action_url` | Char | Computed webhook URL for gather results |

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `render()` | Generate TwiML `<Gather>` with `<Say>` prompt |
| `gather_action()` | Webhook: process DTMF/speech input, route to extension |
| `_get_gather_action_url()` | Compute gather action webhook URL |
| `on_call_action()` | Handle call action from gather input |

---

### 10. twiml.py - `connect.twiml` (NEW model, 100% Twilio)

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
| `exten` | Many2one | `connect.exten` |
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
| `create_extension()` | Create associated `connect.exten` |
| `create()` | Override: create Twilio app on record creation |
| `write()` | Override: update Twilio app on change |
| `unlink()` | Override: delete Twilio app on removal |

---

### 11. domain.py - `connect.domain` (NEW model, 100% Twilio)

Twilio SIP domain management for SIP trunking.

**Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `sid` | Char | Twilio SIP Domain SID |
| `application` | Many2one | `connect.twiml` |
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

### 12. whatsapp_sender.py - `connect.whatsapp_sender` (NEW model, 100% Twilio)

Twilio WhatsApp sender/business account management.

**Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `sid` | Char | Twilio Sender SID |
| `number` | Char | WhatsApp phone number |
| `status` | Char | |
| `url` | Char | |
| `offline_reasons` | Char | |
| `number_id` | Many2one | `connect.number` |
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
| `voice_application` | Many2one | `connect.twiml` |
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

### 13. message_content_template.py (NEW model, 100% Twilio)

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
| `connect.twiml` | Read | Full | - |
| `connect.domain` | Read | Full | - |
| `connect.whatsapp_sender` | Read | Full | - |
| `connect.message_content_template` | Read | Full | - |

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
| `views/settings_views.xml` | `connect.connect_settings_form` | Add Twilio balance group, API keys page, development page, fetch_call_prices |
| `views/user_views.xml` | `connect.view_connect_user_form`, `connect.view_connect_user_tree` | Add SIP/Client phone tab, domain, edge, whatsapp_sender, application; list adds sip_enabled/client_enabled columns |
| `views/number_views.xml` | `connect.view_connect_number_form`, `connect.view_connect_number_tree` | Add twiml routing option and twiml column |
| `views/outgoing_callerid_views.xml` | `connect.view_connect_outgoing_callerid_form` | Add Validate button and validation_code field |

### New Views

| File | Description |
|------|-------------|
| `views/twiml_views.xml` | List + form + search for TwiML apps (ACE code editor, extension, code_type) |
| `views/domain_views.xml` | List + form for SIP domains (subdomain, application, edge_domains) |
| `views/whatsapp_sender_views.xml` | List + form for WhatsApp senders (profile, status, sync) |
| `views/message_content_template_views.xml` | List + form + search for WhatsApp templates (approval workflow) |
| `wizard/whatsapp_composer_views.xml` | WhatsApp message sending wizard form (sender, phone, template, body) |

### Menu Items

Added under PBX menu:
- TwiML (sequence 60)
- Domains (sequence 70)

Added under Messages menu:
- WhatsApp Templates (sequence 64)
- WhatsApp Senders (sequence 65)

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
