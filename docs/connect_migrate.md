# Connect Module Migration Plan

## Status: IMPLEMENTED

The migration has been fully implemented. Both modules are complete with models, views, security, controllers, wizards, and data files.

## Overview

Migrate the monolithic `connect` module from `connect_addons/19.0/connect` (Twilio-only) into a
modular architecture:

- **`connect`** (base) - Technology-agnostic core: calls, messages, users, recordings, routing
- **`connect_twilio`** (new) - Twilio-specific: API client, webhooks, TwiML, SIP domains, WhatsApp
- **`connect_freeswitch`** (existing) - FreeSWITCH-specific: XML-RPC, Verto WebRTC

The pattern follows what `connect_freeswitch` already does: extend base models via `_inherit`.

---

## Source Module Analysis

**Old module:** `../connect_addons/19.0/connect` (monolithic, Twilio-coupled)

| Model | Lines | Twilio Coupling |
|-------|-------|-----------------|
| `settings.py` | 820 | Heavy (REST client, sync, originate via Twilio API) |
| `user.py` | 624 | Heavy (SIP credentials, JWT tokens, TwiML rendering) |
| `call.py` | 555 | Heavy (webhook handlers, CallSid, price fetching) |
| `message.py` | 432 | Heavy (Twilio message API, MessagingResponse) |
| `domain.py` | 635 | 100% Twilio (SIP domain management) |
| `twiml.py` | 299 | 100% Twilio (TwiML app management) |
| `whatsapp_sender.py` | 384 | 100% Twilio (messaging.twilio.com API) |
| `channel.py` | 245 | Heavy (SID-based lookup, SIP URI parsing) |
| `number.py` | 174 | Heavy (Twilio number sync, webhook URLs) |
| `recording.py` | 272 | Heavy (Twilio recording URLs, OpenAI transcription) |
| `outgoing_callerid.py` | 209 | Heavy (Twilio validation, sync) |
| `callflow.py` | ~120 | Medium (TwiML Gather generation) |
| `exten.py` | ~150 | Light (routing abstraction) |
| `res_partner.py` | ~80 | None (partner number search) |
| `res_users.py` | ~30 | None (connect_user link) |
| `message_configuration.py` | ~30 | None (routing config) |
| `debug.py` | ~20 | None |
| `favorite.py` | ~40 | None |

**Controllers:** `twilio_webhooks.py` (122 lines) - All Twilio webhook endpoints

**Frontend:** Phone widget, active calls, phone field, mail service extensions

---

## Target Architecture

### Current State (connect_addons_ng)

```
connect/                          # Base module (minimal)
  models/
    call.py                       # 20 lines - basic call
    endpoint.py                   # 11 lines - basic endpoint
    user.py                       # 12 lines - basic user
    settings.py                   # 54 lines - singleton settings

connect_freeswitch/               # FreeSWITCH extension
  models/
    endpoint.py                   # _inherit connect.endpoint + SIP/WebRTC fields
    settings.py                   # _inherit connect.settings + socket URL
  controllers/
    freeswitch_xml.py             # XML-RPC for FreeSWITCH config
    webrtc.py                     # WebRTC config endpoint
  static/src/                     # Verto client + Phone UI
```

### Target State (after migration)

```
connect/                          # Core module (technology-agnostic)
  models/
    call.py                       # Full call tracking (no Twilio SIDs)
    channel.py                    # Call legs (no Twilio SIDs)
    message.py                    # SMS/WhatsApp messages (no Twilio API)
    recording.py                  # Recordings + OpenAI transcription (not Twilio-specific)
    user.py                       # PBX user profile (no Twilio credentials)
    endpoint.py                   # Generic endpoint (keep as-is)
    settings.py                   # Base settings + OpenAI config (no Twilio keys)
    number.py                     # Inbound DID numbers (no Twilio sync)
    outgoing_callerid.py          # Outbound caller IDs (no Twilio sync)
    exten.py                      # Extension routing
    callflow.py                   # IVR/Gather (abstract, no TwiML)
    callflow_choice.py            # IVR choices
    debug.py                      # Debug log
    res_partner.py                # Partner phone search extensions
    res_users.py                  # res.users connect_user link
    message_configuration.py      # Message routing config
    mail.py                       # mail.message extensions
  controllers/
    main.py                       # Recording proxy, generic endpoints
  wizard/
    transfer.py                   # Transfer wizard
    sms_composer.py               # SMS composer (calls abstract send())
  security/
    groups.xml                    # Keep existing groups
    access_rules.xml              # Access rules for all new models
    record_rules.xml              # Record rules
  views/
    (views for all core models)
  data/
    data.xml                      # Default data
    res_users.xml                 # Webhook user
    ir_cron.xml                   # Scheduled jobs

connect_twilio/                   # Twilio extension (NEW)
  __manifest__.py
  __init__.py
  models/
    __init__.py
    settings.py                   # _inherit + Twilio credentials, client, sync
    user.py                       # _inherit + SIP creds, JWT, TwiML rendering
    call.py                       # _inherit + call_sid, price, webhook handler
    channel.py                    # _inherit + sid, Twilio SIP URI parsing
    message.py                    # _inherit + Twilio send/receive, MessagingResponse
    recording.py                  # _inherit + Twilio recording SIDs, webhook handler
    number.py                     # _inherit + Twilio number sync, webhook URLs
    outgoing_callerid.py          # _inherit + Twilio validation, sync
    callflow.py                   # _inherit + TwiML Gather generation
    twiml.py                      # NEW model: connect.twiml (100% Twilio)
    domain.py                     # NEW model: connect.domain (100% Twilio)
    whatsapp_sender.py            # NEW model: connect.whatsapp_sender (100% Twilio)
    message_content_template.py   # NEW model: WhatsApp templates (100% Twilio)
  controllers/
    __init__.py
    twilio_webhooks.py            # All /twilio/webhook/* routes
  wizard/
    whatsapp_composer.py          # WhatsApp composer (Twilio send)
  security/
    groups.xml                    # Webhook group
    access_rules.xml              # Access for Twilio-only models
    record_rules.xml
  views/
    (views for Twilio-specific models + extensions)
  data/
    twiml.xml                     # Default TwiML apps
    whatsapp_templates.xml        # Default WhatsApp templates
  static/src/                     # Twilio Voice SDK phone widget
    components/phone/             # Phone UI (adapted from old module)
    js/main.js                    # Twilio Device initialization
    js/utils.js                   # Utilities
    widgets/phone_field/          # Phone click-to-call field
    services/                     # Active calls, mail extensions

connect_freeswitch/               # FreeSWITCH extension (existing, unchanged)
  (no changes needed)
```

---

## Detailed Field & Method Split

### 1. connect.settings

**Core fields (connect/models/settings.py):**
```python
name                        # Computed
debug_mode                  # Boolean
number_search_operation     # Selection (=/like)
proxy_recordings            # Boolean
transcript_calls            # Boolean
transcript_provider         # Selection (openai)
summary_prompt              # Text
register_summary            # Boolean
instance_uid                # Char (computed)
api_url                     # Char (computed)
api_fallback_url            # Char
web_base_url                # Char (computed)
module_version              # Char (computed)
odoo_version                # Char (computed)
installation_date           # Datetime (computed)
call_duration_limit         # Integer (computed)
# Registration fields
customer_code, registration_number, registration_key,
is_registered, i_agree_*, admin_name, admin_phone,
admin_email, company_name, company_country, latest_versions
# OpenAI fields (transcription is technology-agnostic)
openai_api_key              # Char (groups restricted)
display_openai_api_key      # Char (masked)
```

**Core methods:**
```python
get_param(), set_param()              # Singleton access
open_settings_form()                  # UI action
connect_notify()                      # Bus notification
connect_reload_view()                 # Bus reload
set_defaults()                        # Installation defaults
set_instance_uid()                    # UUID generation
register_instance()                   # Registration
update_instance_registration()        # Registration update
prepare_registration_data()           # Registration helper
update_usage()                        # Usage tracking
make_usage_request()                  # API helper
check_api_url()                       # URL validation
reformat_numbers_button()             # Partner number cleanup
action_open_system_parameters()       # UI action
check_latest_versions()               # Version check
get_openai_client()                   # OpenAI client (transcription is not Twilio-specific)
```

**Twilio fields (connect_twilio/models/settings.py via _inherit):**
```python
account_sid                 # Char
auth_token                  # Char (groups restricted)
display_auth_token          # Char (masked)
twilio_api_key              # Char
twilio_api_secret           # Char (groups restricted)
display_twilio_api_secret   # Char (masked)
twilio_balance              # Char (readonly)
twilio_region               # Selection (us1/ie1/au1)
twilio_edge                 # Selection
twilio_auto_sync            # Boolean
twilio_verify_requests      # Boolean
fetch_call_prices           # Boolean
```

**Twilio methods:**
```python
get_client()                          # Twilio REST client
sync()                                # Full Twilio sync
originate_call()                      # Click2call via Twilio
get_external_call_route()             # TwiML for external calls
get_twilio_balance()                  # Balance check
_reset_twilio_edge()                  # Onchange handler
```

### 2. connect.call

**Core fields (connect/models/call.py):**
```python
name                        # Char (computed)
channels                    # One2many → connect.channel
recording                   # Many2one → connect.recording (computed)
transcript                  # Text (computed from recording)
recording_widget            # Html (computed from recording)
recording_icon              # Html (computed)
summary                     # Html
called                      # Char
caller                      # Char
parent_call                 # Many2one → connect.call
partner                     # Many2one → res.partner
partner_img                 # Binary (related)
direction                   # Char (incoming/outgoing/internal)
call_type                   # Selection (phone/whatsapp)
status                      # Char
duration                    # Integer (seconds)
duration_minutes            # Float (computed)
duration_human              # Char (computed)
caller_pbx_user             # Many2one → connect.user
answered_pbx_user           # Many2one → connect.user
called_pbx_users            # Many2many → connect.user
caller_user                 # Many2one → res.users
caller_user_img             # Binary (related)
called_users                # Many2many → res.users
answered_user               # Many2one → res.users
answered_user_img           # Binary (related)
scheduled_datetime          # Datetime
voicemail_url               # Char
voicemail_duration          # Integer
voicemail_icon              # Html (computed)
voicemail_widget            # Html (computed)
ref                         # Reference (computed)
has_error                   # Boolean
error_code                  # Char
error_message               # Text
```

**Core methods:**
```python
_get_name()                           # Computed name
_get_ref()                            # Computed reference
_get_recording_data()                 # Computed recording fields
_get_voicemail_widget()               # Computed voicemail player
_get_voicemail_icon()                 # Computed icon
_get_duration_human()                 # Computed duration
register_call()                       # Post to chatter
register_call_post_message()          # Message post helper
register_summary_to_rec()             # Summary to chatter
register_partner_call_summary()       # Constrains handler
create_partner_button()               # UI action
transfer_button()                     # UI action
redial()                              # Calls originate_call
get_widget_calls()                    # Phone widget data
get_widget_fields()                   # Phone widget fields
on_call_action()                      # Generic call action handler
```

**Twilio fields (connect_twilio/models/call.py via _inherit):**
```python
call_sid                    # Char (Twilio CallSid)
price                       # Float
price_unit                  # Char
price_currency              # Char
is_price_fetched            # Boolean
```

**Twilio methods:**
```python
on_call_status()                      # Twilio webhook handler (creates channels/calls)
on_vm_recording_status()              # Voicemail webhook handler
save_call_price()                     # Store CallSid for price fetch
_fetch_call_price_from_api()          # Twilio REST price fetch
fetch_call_prices_batch()             # Cron: batch price fetch
transfer()                            # Twilio call transfer (Conference/SIP)
```

### 3. connect.channel

**Core fields (connect/models/channel.py):**
```python
call                        # Many2one → connect.call
parent_channel              # Many2one → connect.channel
caller                      # Char
called                      # Char
to                          # Char
technical_direction         # Char (inbound/outbound-api/outbound-dial)
status                      # Char
duration                    # Integer
duration_billing            # Integer
duration_human              # Char (computed)
caller_pbx_user             # Many2one → connect.user
called_pbx_user             # Many2one → connect.user
caller_user                 # Many2one → res.users
called_user                 # Many2one → res.users
caller_number               # Char (computed, stripped)
called_number               # Char (computed, stripped)
call_type                   # Selection (phone/whatsapp)
partner                     # Many2one → res.partner
```

**Core methods:**
```python
_get_channel_numbers()                # Parse caller/called into clean numbers
_get_duration_human()                 # Computed duration
```

**Twilio fields (connect_twilio/models/channel.py via _inherit):**
```python
sid                         # Char (Twilio CallSid for this leg)
```

**Twilio methods:**
```python
on_call_status()                      # Twilio webhook: create/update channels
connect_notify()                      # Desktop notification for SIP calls
```

### 4. connect.message

**Core fields (connect/models/message.py):**
```python
name                        # Char (computed)
from_number                 # Char
to_number                   # Char
body                        # Text
num_media                   # Integer
message_type                # Char (sms/WhatsApp/mms)
status                      # Char
direction                   # Selection (incoming/outgoing, computed)
direction_display           # Html (computed)
status_display              # Html (computed)
sender_user                 # Many2one → res.users
sender_user_img             # Binary (related)
partner                     # Many2one → res.partner
partner_img                 # Binary (related)
from_city, from_state       # Char (geographic)
from_zip, from_country      # Char (geographic)
has_error                   # Boolean
error_code                  # Char
error_message               # Char
res_model                   # Char
res_id                      # Integer
ref                         # Reference (computed)
parent_message              # Many2one → connect.message
media_url                   # Char
media_content_type          # Char
media_widget                # Html (computed)
```

**Core methods:**
```python
_compute_name()                       # Computed name
_compute_direction()                  # Direction logic (abstract, no Twilio deps)
_compute_direction_display()          # Icon display
_compute_status_display()             # Status icon
_compute_ref()                        # Reference field
_format_phone_number()                # Phone formatting
_get_media_widget()                   # Media HTML player
_reference_models()                   # Dynamic reference
get_receive_message_values()          # Parse webhook params into values
action_retry()                        # Retry failed messages (calls send())
```

**Twilio fields (connect_twilio/models/message.py via _inherit):**
```python
message_sid                 # Char (Twilio MessageSid)
account_sid                 # Char
messaging_service_sid       # Char
```

**Twilio methods:**
```python
receive()                             # Twilio webhook: incoming SMS/WhatsApp
send()                                # Send via Twilio API
client_send()                         # Low-level Twilio client.messages.create()
_compute_direction()                  # Override: check our Twilio numbers
```

### 5. connect.user

**Core fields (connect/models/user.py):**
```python
name                        # Char (computed)
username                    # Char (required, alphanumeric)
user                        # Many2one → res.users
exten                       # Many2one → connect.exten
exten_number                # Char (related)
callflow                    # One2many → connect.user_callflow
record_calls                # Boolean
voicemail_enabled           # Boolean
voicemail_prompt            # Text (Jinja2 template)
outgoing_callerid           # Many2one → connect.outgoing_callerid
missed_calls_notify         # Boolean
greeting_message            # Char
summary_prompt              # Char
```

**Core methods:**
```python
_get_name()                           # Computed name
_check_username()                     # Constrains
manage_group()                        # Add/remove security groups
get_user_by_exten_number()            # Lookup by extension
get_user_by_uri()                     # Lookup by SIP URI
create_extension()                    # Create connect.exten
render_voicemail_prompt()             # Jinja2 render
get_greeting_message()                # Override point
get_voicemail_prompt()                # Override point
on_call_action()                      # Call action handler (abstract)
_manage_channel_callflow()            # Callflow CRUD
_manage_voicemail_enabled()           # Constrains handler
```

**Twilio fields (connect_twilio/models/user.py via _inherit):**
```python
sid                         # Char (Twilio SIP credential SID)
password                    # Char (SIP password, masked)
domain                      # Many2one → connect.domain
sip_enabled                 # Boolean
sip_priority                # Selection (1/2)
sip_ring_timeout            # Integer
client_enabled              # Boolean
client_priority             # Selection (1/2)
client_ring_timeout         # Integer
uri                         # Char (computed: user@domain)
connect_uri                 # Char (computed: with edge)
application                 # Many2one → connect.twiml
whatsapp_sender_id          # Many2one → connect.whatsapp_sender
twilio_edge                 # Selection
```

**Twilio methods:**
```python
_create_sip_account()                 # Create Twilio SIP credential
_import_existing_sip_credential()     # Import from Twilio
_update_sip_password()                # Update Twilio credential
delete_sip_account()                  # Delete Twilio credential
generate_twilio_password()            # Strong password generator
get_client_token()                    # JWT for Twilio Voice SDK
get_client_identity()                 # SIP identity
render()                              # TwiML rendering (SIP/Client/VM flow)
render_client()                       # TwiML Dial Client
render_sip()                          # TwiML Dial SIP
render_voicemail()                    # TwiML Record
_get_sip_uri()                        # Computed URI
_manage_sip_callflow()                # SIP callflow constrains
_manage_client_callflow()             # Client callflow constrains
_restrict_sip_domain_change()         # Domain change validation
_make_blank_password()                # Onchange
```

### 6. connect.number

**Core fields (connect/models/number.py):**
```python
phone_number                # Char (required, unique)
friendly_name               # Char
is_ignored                  # Boolean
is_default                  # Boolean
destination                 # Selection (user/callflow) - no twiml in core
user                        # Many2one → connect.user
callflow                    # Many2one → connect.callflow
```

**Core methods:**
```python
render()                              # Route to destination
route_call()                          # Main call routing (abstract)
```

**Twilio fields (connect_twilio/models/number.py via _inherit):**
```python
sid                         # Char (Twilio SID)
voice_url                   # Char (computed webhook URLs)
voice_fallback_url          # Char (computed)
voice_status_url            # Char (computed)
message_url                 # Char (computed)
message_fallback_url        # Char (computed)
```

**Twilio methods:**
```python
sync()                                # Twilio → Odoo number sync
update_twilio_number()                # Push config to Twilio
_get_twilio_urls()                    # Computed webhook URLs
route_call()                          # Override: Twilio-specific routing
```

### 7. connect.outgoing_callerid

**Core fields (connect/models/outgoing_callerid.py):**
```python
number                      # Char (required, + format)
friendly_name               # Char
status                      # Char
is_default                  # Boolean
callerid_type               # Selection (outgoing_callerid/number)
```

**Twilio fields (connect_twilio via _inherit):**
```python
sid                         # Char
validation_code             # Char
```

**Twilio methods:**
```python
sync()                                # Twilio → Odoo sync
validate()                            # Start Twilio validation
update_status()                       # Webhook status callback
```

### 8. connect.recording

**Core fields (connect/models/recording.py):**
```python
media_url                   # Char
status                      # Char
duration                    # Integer
duration_human              # Char (computed)
start_time                  # Datetime
call                        # Many2one → connect.call
channel                     # Many2one → connect.channel
partner                     # Many2one → res.partner
caller_user                 # Many2one → res.users
called_user                 # Many2one → res.users
caller_number               # Char
called_number               # Char
recording_widget            # Html (computed audio player)
transcript                  # Text
transcription_token         # Char
transcription_error         # Char
transcription_price         # Char
summary                     # Html
list_view_summary           # Html (computed truncated)
price                       # Char
price_unit                  # Char
source                      # Char
```

**Core methods:**
```python
_get_duration_human()                 # Computed duration
_get_recording_widget()               # HTML audio player
_get_list_view_summary()              # Truncated summary for list views
_sync_summary()                       # Constrains: sync summary to call record
get_transcript()                      # Trigger transcription workflow
transcribe_recording()                # OpenAI Whisper API call (technology-agnostic)
make_summary()                        # OpenAI GPT-4o summary (technology-agnostic)
update_transcript()                   # Async callback handler
```

**Note:** OpenAI transcription methods (`transcribe_recording()`, `make_summary()`) live
in core because they are NOT Twilio-specific. Any integration module that creates a
recording with a `media_url` can trigger transcription. The `openai` Python package is
a core dependency.

**Twilio fields (connect_twilio via _inherit):**
```python
sid                         # Char (Twilio Recording SID)
call_sid                    # Char (Twilio CallSid)
```

**Twilio methods:**
```python
on_recording_status()                 # Twilio webhook handler
prepare_data()                        # Parse Twilio webhook params
sync()                                # Twilio → Odoo sync
create()                              # Override: set sid/call_sid from Twilio params
```

### 9. connect.callflow

**Core fields (connect/models/callflow.py):**
```python
name                        # Char
exten                       # Many2one → connect.exten
language                    # Char (default en-US)
voice                       # Char (default Woman)
gather_input                # Boolean
gather_input_type           # Selection (dtmf/speech/both)
gather_timeout              # Integer
gather_digits               # Integer
gather_hints                # Char
prompt_message              # Text
invalid_input_message       # Text
choices                     # One2many → connect.callflow_choice
ring_users                  # Many2many → connect.user
record_calls                # Boolean
voicemail_enabled           # Boolean
voicemail_prompt            # Text
```

**Core methods:**
```python
render()                              # Abstract: generate call flow response
create_extension()                    # Create connect.exten
```

**Twilio methods (connect_twilio via _inherit):**
```python
render()                              # Override: TwiML Gather generation
gather_action()                       # Twilio DTMF/speech webhook
gather_action_url                     # Computed webhook URL
```

### 10. Twilio-Only Models (connect_twilio only)

#### connect.twiml
Full model, 100% Twilio. TwiML application management.
```python
sid, old_sid, name, description, code_type, twiml, twipy,
model, method, voice_url, voice_fallback_url, voice_status_url,
exten, exten_number
```

#### connect.domain
Full model, 100% Twilio. SIP domain management.
```python
sid, subdomain, friendly_name, domain_name, edge_domains,
cred_list_sid, application, sip_registration, delete_protection
```

#### connect.whatsapp_sender
Full model, 100% Twilio. WhatsApp business accounts.
```python
sid, number, status, url, offline_reasons, profile_*,
messaging_limit, quality_rating, number_id, voice_application,
callback_url, status_callback_url, is_default, no_sync
```

#### connect.message_content_template
Full model, 100% Twilio. WhatsApp message templates.

### 11. Supporting Models

**connect.user_callflow** and **connect.user_callflow_call** stay in core.

**connect.exten** stays in core (routing abstraction).

**connect.callflow_choice** stays in core.

**connect.debug** stays in core.

**connect.favorite** stays in core.

**connect.message_configuration** stays in core.

---

## Implementation Steps

### Phase 1: Expand Core `connect` Module

Add all core models, views, security, and data to the base `connect` module.

#### Step 1.1: Core Models

Create/expand these files in `connect/models/`:

1. **call.py** - Expand from 20 lines to full call tracking:
   - Add all core fields listed above (channels, recording, duration, partner, etc.)
   - Add `_inherit = ['mail.thread', 'mail.activity.mixin']`
   - Add computed fields (`_get_name`, `_get_duration_human`, `_get_recording_data`, etc.)
   - Add `register_call()`, `create_partner_button()`, `get_widget_calls()`
   - Do NOT add: `call_sid`, `price*`, `is_price_fetched`, `on_call_status()`, `transfer()`

2. **channel.py** (NEW) - Call legs:
   - All core fields (call, parent_channel, caller, called, direction, status, duration, users)
   - `_get_channel_numbers()` - generic number parsing (without Twilio SIP URI specifics)
   - Do NOT add: `sid`, `on_call_status()`, `connect_notify()`

3. **message.py** (NEW) - Messages:
   - All core fields (from/to, body, status, direction, media, partner, etc.)
   - All computed methods (name, direction, status display, media widget)
   - `get_receive_message_values()` as a generic parser
   - Do NOT add: `message_sid`, `account_sid`, `receive()`, `send()`, `client_send()`

4. **recording.py** (NEW) - Recordings:
   - All core fields (media_url, duration, call, channel, transcript, summary, transcription_*)
   - Computed widget/duration methods
   - OpenAI transcription: `transcribe_recording()`, `make_summary()`, `get_transcript()`, `update_transcript()`
   - Note: Transcription is technology-agnostic (uses OpenAI, not Twilio) so it belongs in core
   - Do NOT add: `sid`, `call_sid`, `on_recording_status()`

5. **user.py** - Expand from 12 lines:
   - Add: username, callflow, exten, record_calls, voicemail, outgoing_callerid, greeting, etc.
   - Add: manage_group(), get_user_by_*, render_voicemail_prompt()
   - Keep: user_id (→ `user` field matching old module)
   - Do NOT add: sid, password, domain, sip_*, client_*, twilio_edge, render_*()

6. **user_callflow.py** (NEW):
   - `connect.user_callflow` model
   - `connect.user_callflow_call` model

7. **number.py** (NEW) - DIDs:
   - Core fields: phone_number, friendly_name, destination, user, callflow
   - `render()` - route to destination
   - Do NOT add: sid, voice_url, sync(), update_twilio_number()

8. **outgoing_callerid.py** (NEW):
   - Core fields: number, friendly_name, status, is_default, callerid_type
   - Do NOT add: sid, sync(), validate()

9. **exten.py** (NEW) - Extension routing:
   - number, model, res_id, dst (computed reference)
   - render() - route to destination
   - create_extension() factory

10. **callflow.py** (NEW) - IVR:
    - All core fields (name, language, voice, gather_*, choices, ring_users, etc.)
    - Abstract render() (to be overridden by Twilio/FreeSWITCH)

11. **callflow_choice.py** (NEW):
    - choice_digits, speech, exten

12. **debug.py** (NEW):
    - model, message fields

13. **settings.py** - Expand:
    - Add all core fields and methods listed above
    - Add connect_notify(), connect_reload_view()
    - Add registration, usage tracking
    - Add OpenAI fields: openai_api_key, display_openai_api_key, get_openai_client()
    - Note: OpenAI config is in core because transcription is not Twilio-specific
    - Do NOT add Twilio credentials or Twilio client methods

14. **res_partner.py** (NEW):
    - `_inherit = 'res.partner'`
    - `get_partner_by_number()` method
    - `connect_calls_count`, `connect_messages_count` computed fields
    - `create_record_from_message()` method

15. **res_users.py** (NEW):
    - `_inherit = 'res.users'`
    - `connect_user` field (Many2one)
    - `pin_code` field

16. **message_configuration.py** (NEW):
    - number (Many2one), destination, default_values

17. **mail.py** (NEW):
    - `_inherit = 'mail.message'`
    - `connect_message` field (Many2one)

#### Step 1.2: Core Views

Create views for all new models in `connect/views/`:
- `call.xml` - Tree/form with recording widgets, partner button
- `channel.xml` - Tree/form
- `message.xml` - Tree/form with media widgets
- `recording.xml` - Tree/form with audio player, transcript
- `number.xml` - Tree/form with destination routing
- `outgoing_callerid.xml` - Tree/form
- `exten.xml` - Tree/form
- `callflow.xml` - Form with choices/gather config
- `debug.xml` - Tree (read-only)
- `res_partner.xml` - Inherit partner form (add call/message counts)
- `user_views.xml` - Expand existing user form
- `settings.xml` - Expand existing settings form
- `menu.xml` - Expand menu structure

**Menu structure:**
```
Connect
  ├── Calls (seq 10)
  ├── Messages (seq 20)
  ├── Recordings (seq 30)
  ├── Users (seq 40)
  ├── Numbers (seq 50)
  ├── Caller IDs (seq 60)
  ├── Call Flows (seq 70)
  ├── Extensions (seq 80)
  ├── Configuration
  │   ├── Settings (seq 10)
  │   ├── Message Config (seq 20)
  │   └── Debug Log (seq 30)
```

#### Step 1.3: Core Security

Expand security files:
- Add access rules for all new models (call, channel, message, recording, number, etc.)
- Add record rules (users see own records, admins see all)
- Add webhook group definition (needed for Twilio module later)

#### Step 1.4: Core Data

- `data/res_users.xml` - Webhook user (connect.user_connect_webhook)
- `data/data.xml` - Default records, instance UID setup
- `data/ir_cron.xml` - Cron jobs (usage tracking, price fetch stub)

#### Step 1.5: Core Controllers

- `controllers/main.py` - Recording proxy endpoint, generic helpers

#### Step 1.6: Core Wizards

- `wizard/transfer.py` - Transfer wizard (stub/generic)
- `wizard/sms_composer.py` - SMS composer (inherits sms.composer, calls abstract send() on connect.message)

#### Step 1.7: Update __manifest__.py

- Add depends: `['base', 'mail', 'contacts']`
- Add all new data/view/security files
- Keep `application: True`

---

### Phase 2: Create `connect_twilio` Module

#### Step 2.1: Module Structure

```
connect_twilio/
  __init__.py
  __manifest__.py             # depends: ['connect']
  models/__init__.py
  controllers/__init__.py
  wizard/__init__.py
  security/
  views/
  data/
  static/src/
```

**__manifest__.py:**
```python
{
    'name': 'Oduist Connect Twilio',
    'version': '19.0.1.0.0',
    'category': 'Phone',
    'summary': 'Twilio integration for Oduist Connect',
    'depends': ['connect'],
    'external_dependencies': {
        'python': ['twilio'],
    },
    'data': [
        'security/groups.xml',
        'security/access_rules.xml',
        'data/twiml.xml',
        'data/whatsapp_templates.xml',
        'views/settings.xml',
        'views/domain.xml',
        'views/twiml.xml',
        'views/user.xml',
        'views/number.xml',
        'views/outgoing_callerid.xml',
        'views/whatsapp_sender.xml',
        'views/call.xml',
        'views/recording.xml',
        'views/message.xml',
        'wizard/whatsapp_composer_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'connect_twilio/static/src/...',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
```

#### Step 2.2: Twilio Models (all use _inherit)

Each file extends the corresponding core model:

1. **settings.py** - `_inherit = 'connect.settings'`
   - Add Twilio credential fields
   - Add `get_client()` (Twilio REST client)
   - Add `sync()`, `originate_call()`, `get_twilio_balance()`
   - Override `write()` for protected fields masking

2. **call.py** - `_inherit = 'connect.call'`
   - Add `call_sid`, `price*`, `is_price_fetched`
   - Add `on_call_status()`, `on_vm_recording_status()`
   - Add `save_call_price()`, `_fetch_call_price_from_api()`, `fetch_call_prices_batch()`
   - Add `transfer()` with Twilio Conference

3. **channel.py** - `_inherit = 'connect.channel'`
   - Add `sid` field
   - Add `on_call_status()` - create/update channels from Twilio params
   - Add `connect_notify()` - desktop notification
   - Override `_get_channel_numbers()` for Twilio SIP URI parsing

4. **message.py** - `_inherit = 'connect.message'`
   - Add `message_sid`, `account_sid`, `messaging_service_sid`
   - Add `receive()` - Twilio webhook handler
   - Add `send()`, `client_send()` - Twilio message API
   - Override `_compute_direction()` to check Twilio numbers

5. **recording.py** - `_inherit = 'connect.recording'`
   - Add `sid`, `call_sid`
   - Add `on_recording_status()`, `prepare_data()`, `sync()`
   - Note: transcription methods (transcribe_recording, make_summary) are in CORE, not here

6. **user.py** - `_inherit = 'connect.user'`
   - Add Twilio SIP fields (sid, password, domain, sip_*, client_*, twilio_edge)
   - Add TwiML rendering (render(), render_client(), render_sip(), render_voicemail())
   - Add Twilio credential management (_create_sip_account, _update_sip_password, etc.)
   - Add JWT token generation (get_client_token(), get_client_identity())

7. **number.py** - `_inherit = 'connect.number'`
   - Add `sid`, webhook URL fields
   - Add `sync()`, `update_twilio_number()`
   - Override `route_call()` for Twilio call flow

8. **outgoing_callerid.py** - `_inherit = 'connect.outgoing_callerid'`
   - Add `sid`, `validation_code`
   - Add `sync()`, `validate()`, `update_status()`

9. **callflow.py** - `_inherit = 'connect.callflow'`
   - Override `render()` with TwiML Gather generation
   - Add `gather_action()` webhook handler
   - Add `gather_action_url` computed field

10. **twiml.py** - NEW model `connect.twiml`
    - Full Twilio TwiML application management
    - sid, name, code_type, twiml/twipy, voice URLs
    - create_twilio_app(), update_twilio_app(), sync()
    - render(), render_twiml(), render_python()

11. **domain.py** - NEW model `connect.domain`
    - Full Twilio SIP domain management
    - sid, subdomain, cred_list_sid, application
    - create_twilio_sip_domain(), sync(), route_call()
    - originate_external_call(), originate_whatsapp_call()

12. **whatsapp_sender.py** - NEW model `connect.whatsapp_sender`
    - Full Twilio WhatsApp sender management
    - sync(), send_whatsapp(), update_message_status()

13. **message_content_template.py** - NEW model
    - WhatsApp content templates from Twilio

#### Step 2.3: Twilio Controller

`controllers/twilio_webhooks.py`:
- Copy from old module with all routes under `/twilio/webhook/`
- Signature validation via `twilio.request_validator`
- All routes delegate to model methods

#### Step 2.4: Twilio Wizards

- `wizard/whatsapp_composer.py` - WhatsApp message sending
- Note: `sms_composer.py` is in CORE (connect/wizard/) since it calls the abstract send() method

#### Step 2.5: Twilio Views

Inherit and extend core views:
- Settings: Add Twilio credentials tab, sync buttons
- User: Add SIP/Client config, domain, edge selection
- Number: Add SID, webhook URLs display
- Call: Add price fields, CallSid
- Recording: Add transcription fields

New views for Twilio-only models:
- TwiML apps list/form
- SIP Domains list/form
- WhatsApp Senders list/form

#### Step 2.6: Twilio Security

- Webhook user access rules
- Access rules for connect.twiml, connect.domain, connect.whatsapp_sender

#### Step 2.7: Twilio Data

- `data/twiml.xml` - Default TwiML apps (SIP domain handler, number handler)
- `data/whatsapp_templates.xml` - Default WhatsApp message templates

#### Step 2.8: Twilio Frontend

Move the phone widget from old module:
- `static/src/components/phone/` - Phone UI (Twilio Voice SDK)
- `static/src/js/main.js` - Twilio Device init, token refresh
- `static/src/js/utils.js` - Utilities
- `static/src/widgets/phone_field/` - Click-to-call field
- `static/src/services/` - Active calls, mail extensions

---

### Phase 3: Adapt `connect_freeswitch`

Minimal changes needed since connect_freeswitch already follows the `_inherit` pattern.

1. **Verify compatibility** - Ensure new core fields don't conflict with FreeSWITCH extensions
2. **Update imports** - If any new core model fields overlap, adjust
3. **Test** - FreeSWITCH XML-RPC and WebRTC should work unchanged

---

## Implementation Order

1. **Phase 1.1** - Core models (Python files only, no views)
2. **Phase 1.2** - Core views
3. **Phase 1.3-1.4** - Core security + data
4. **Phase 1.5-1.7** - Core controllers, wizards, manifest
5. **Phase 2.1-2.2** - Twilio module structure + models
6. **Phase 2.3-2.4** - Twilio controllers + wizards
7. **Phase 2.5-2.8** - Twilio views, security, data, frontend
8. **Phase 3** - FreeSWITCH compatibility check

---

## Key Design Decisions

### 1. `connect.number.destination` field

The old module uses `destination = Selection([user/callflow/twiml])` with `twiml` being
Twilio-specific. In core, rename `twiml` → `application` to be generic. Each integration
module (Twilio/FreeSWITCH) can interpret what "application" means.

### 2. Callflow rendering

Core `connect.callflow.render()` should be abstract (raise NotImplementedError or return empty).
`connect_twilio` overrides it with TwiML Gather. `connect_freeswitch` could override it with
FreeSWITCH dialplan XML in the future.

### 3. User rendering

Core `connect.user` does NOT have `render()`. The old render() is 100% TwiML-based.
`connect_twilio` adds render/render_client/render_sip/render_voicemail.
`connect_freeswitch` already handles this via its XML-RPC controller.

### 4. Channel creation

Core `connect.channel` is a data model only. The `on_call_status()` webhook handler
that creates channels belongs in `connect_twilio`. FreeSWITCH would create channels
via its own event handlers.

### 5. Message send/receive

Core `connect.message` stores messages but has no send/receive. Each integration
module adds its own send/receive methods. This allows future integrations
(e.g., connect_vonage, connect_bandwidth) to use the same message model.

### 6. Settings singleton

The core singleton pattern (`get_param/set_param`) stays in core. Each module adds
its own fields. The `open_settings_form()` should render a unified form with tabs
per module.

### 7. Webhook user

The `connect.user_connect_webhook` (special res.users for webhook processing)
stays in core since it's used by any integration's webhook handlers.

### 8. Number model references

In the core module, `connect.number.twiml` field should be renamed to a more generic
reference (or dropped). The `destination` selection can be extended by each module.
For the Twilio module, the selection adds 'twiml' option.

---

## File Mapping Reference

Source → Target mapping for every file in the old module:

| Old File | → Core (connect/) | → Twilio (connect_twilio/) |
|----------|-------------------|--------------------------|
| `models/settings.py` | settings.py (base fields + OpenAI config) | settings.py (_inherit + Twilio credentials) |
| `models/call.py` | call.py (tracking + chatter) | call.py (_inherit + webhooks) |
| `models/channel.py` | channel.py (data model) | channel.py (_inherit + sid) |
| `models/message.py` | message.py (data model) | message.py (_inherit + API) |
| `models/recording.py` | recording.py (data + OpenAI transcription) | recording.py (_inherit + SIDs/webhooks) |
| `models/user.py` | user.py (profile + callflow) | user.py (_inherit + SIP/TwiML) |
| `models/number.py` | number.py (routing) | number.py (_inherit + sync) |
| `models/outgoing_callerid.py` | outgoing_callerid.py (data) | outgoing_callerid.py (_inherit) |
| `models/callflow.py` | callflow.py + callflow_choice.py | callflow.py (_inherit + TwiML) |
| `models/exten.py` | exten.py | - |
| `models/twiml.py` | - | twiml.py (new model) |
| `models/domain.py` | - | domain.py (new model) |
| `models/whatsapp_sender.py` | - | whatsapp_sender.py (new model) |
| `models/message_configuration.py` | message_configuration.py | - |
| `models/message_content_template.py` | - | message_content_template.py |
| `models/debug.py` | debug.py | - |
| `models/favorite.py` | - (deferred) | - |
| `models/res_partner.py` | res_partner.py | - |
| `models/res_users.py` | res_users.py | - |
| `models/mail.py` | mail.py | - |
| `models/scheduled_call.py` | - (deferred) | - |
| `models/documentation.py` | - (deferred) | - |
| `controllers/twilio_webhooks.py` | - | twilio_webhooks.py |
| `controllers/main.py` | main.py (recording proxy) | - |
| `wizard/transfer.py` | transfer.py | - |
| `wizard/sms_composer.py` | sms_composer.py (abstract send) | - |
| `wizard/whatsapp_composer.py` | - | whatsapp_composer.py |
| `static/src/*` | - | static/src/* (Twilio Voice SDK) |

---

## Dependencies

```
connect (base)
  ├── depends: ['base', 'mail', 'contacts']
  ├── python: ['phonenumbers', 'jinja2', 'openai']
  │
  ├── connect_twilio
  │   ├── depends: ['connect']
  │   ├── python: ['twilio']
  │   │
  │   └── (future: connect_twilio_elevenlabs)
  │       └── depends: ['connect_twilio']
  │
  ├── connect_freeswitch
  │   ├── depends: ['connect', 'web']
  │   │
  │   └── (future: connect_freeswitch_webrtc_advanced)
  │
  └── (future: connect_asterisk)
      └── depends: ['connect']
```
