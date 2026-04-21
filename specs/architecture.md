# Connect Architecture Specification

## Design Principles

1. **Core `connect` is technology-agnostic.** It stores data, provides UI, handles chatter
   integration, and defines abstract interfaces. It never imports `twilio`, never references
   Twilio-specific concepts (SIDs, TwiML, etc.), and never imports FreeSWITCH-specific code.

2. **Integration modules extend core via `_inherit`.** Modules like `connect_twilio` and
   `connect_freeswitch` add provider-specific fields, methods, and webhook handlers to
   the core models. They never redefine core models.

3. **OpenAI transcription is in core (not Twilio-specific).** Recording transcription via
   OpenAI Whisper and call summarization via GPT-4o are technology-agnostic features.
   Any telephony provider can produce a recording; any recording can be transcribed.
   The `openai` Python package is a core dependency, and `openai_api_key` +
   `get_openai_client()` live in `connect.settings`.

4. **SMS composer is in core.** The `sms_composer.py` wizard lives in core `connect`
   and calls the abstract `connect.message.send()` method. The actual send implementation
   is provided by whichever integration module is installed. This allows the same composer
   UI to work with Twilio, or any future SMS provider.

5. **Each integration module implements:** webhook handlers, API client initialization,
   protocol-specific rendering (TwiML, FreeSWITCH XML, etc.), provider-specific
   synchronization, and provider credential management.

6. **Webhook user is in core.** The special `connect.user_connect_webhook` res.users record
   is defined in core data. All integration modules use it when processing webhook callbacks
   to create/update records with proper permissions.

7. **Settings form uses notebook tabs.** The core settings form defines the base structure
   with a notebook widget. Each integration module adds its own page/tab (e.g., "Twilio"
   tab, "FreeSWITCH" tab) via view inheritance.

---

## Extension Pattern

The fundamental pattern for all models:

```
Core model (connect/models/foo.py):
    _name = 'connect.foo'

    # Data fields (stored in database)
    name = fields.Char(...)
    status = fields.Char(...)

    # Computed fields (display helpers)
    duration_human = fields.Char(compute='_get_duration_human')

    # UI methods
    def create_partner_button(self): ...
    def get_widget_calls(self): ...

    # Business logic (technology-agnostic)
    def register_call(self): ...

    # Abstract methods (no implementation - raise NotImplementedError or pass)
    def route_call(self): ...
    def send(self): ...


Integration model (connect_twilio/models/foo.py):
    _inherit = 'connect.foo'

    # Provider-specific fields
    sid = fields.Char(string='Twilio SID')
    call_sid = fields.Char(string='Call SID')

    # Provider-specific methods
    def on_call_status(self, params):
        """Twilio webhook handler"""
        ...

    def sync(self):
        """Sync from Twilio API"""
        client = self.env['connect.settings'].get_client()
        ...

    # Override abstract methods
    def route_call(self):
        """Generate TwiML response for call routing"""
        ...

    def send(self):
        """Send message via Twilio API"""
        client = self.env['connect.settings'].get_client()
        client.messages.create(...)
```

---

## Key Boundaries

### What lives in Core (`connect`)

| Category | Examples |
|----------|---------|
| Data models | call, channel, message, recording, user, number, callflow, exten |
| Computed fields | duration_human, recording_widget, direction_display |
| Chatter integration | register_call(), register_summary_to_rec() |
| Phone number handling | phonenumbers library, strip_number(), format_number() |
| Partner integration | get_partner_by_number(), create_record_from_message() |
| OpenAI transcription | transcribe_recording(), make_summary(), get_openai_client() |
| SMS composition | sms_composer.py wizard (calls abstract send()) |
| Recording proxy | _serve_media() controller (abstract auth) |
| Voicemail rendering | render_voicemail_prompt() via Jinja2 |
| Security groups | group_user, group_admin, group_webhook |
| Webhook user | connect.user_connect_webhook |
| UI views | All base views, menu structure |
| Settings | Registration, usage tracking, OpenAI config |

### What lives in Integration Modules (`connect_twilio`, `connect_freeswitch`)

| Category | Examples |
|----------|---------|
| API client | get_client() for Twilio REST / freeswitch_api() for FreeSWITCH XML-RPC |
| Webhook handlers | on_call_status(), receive(), on_recording_status() |
| Protocol rendering | TwiML generation, FreeSWITCH XML dialplan |
| Provider sync | sync() methods for numbers, callerIDs, domains |
| Credential management | SIP accounts, API keys, JWT tokens |
| Provider-specific models | connect.twiml, connect.domain, connect.whatsapp_sender |
| Frontend SDK | Twilio Voice SDK phone widget, Verto WebRTC client |
| Message sending | send() implementation via provider API |
| Provider-specific fields | SIDs, webhook URLs, provider-specific status codes |

### Explicit Boundary Rules

1. **Core NEVER imports `twilio`** or any Twilio-specific Python package.
2. **Core NEVER imports FreeSWITCH-specific** code or ESL libraries.
3. **Message send/receive** is split: core stores messages + provides composer UI;
   integration modules implement `send()` and `receive()` webhook handlers.
4. **Webhook handlers** for calls, recordings, and messages are 100% in integration modules.
5. **Recording proxy** (`_serve_media`) has its routing structure in core, but uses
   abstract auth that the integration module overrides (e.g., Twilio basic auth with
   account_sid/auth_token).
6. **SIP credential management** (create/update/delete SIP accounts) is 100% in the
   integration module.
7. **Call routing** (`route_call()`) is abstract in core; each integration module provides
   its own implementation (TwiML for Twilio, XML for FreeSWITCH).
8. **Callflow rendering** is abstract in core (stores config only); integration modules
   render to their protocol.

---

## Model Dependency Graph

```
connect.settings (singleton)
    |
    +-- connect.number (inbound DIDs)
    |       |
    |       +-- connect.message_configuration
    |
    +-- connect.outgoing_callerid (outbound caller IDs)
    |
    +-- connect.user (PBX users)
    |       |
    |       +-- connect.user_callflow
    |       |       |
    |       |       +-- connect.user_callflow_call
    |       |
    |       +-- connect.endpoint (optional link)
    |       |
    |       +-- connect.exten (extension routing)
    |
    +-- connect.endpoint (can also be standalone, without user)
    |
    +-- connect.callflow (IVR)
    |       |
    |       +-- connect.callflow_choice
    |       |
    |       +-- connect.exten
    |
    +-- connect.call
    |       |
    |       +-- connect.channel (call legs)
    |       |
    |       +-- connect.recording
    |               |
    |               +-- (OpenAI transcription)
    |
    +-- connect.message
    |
    +-- connect.debug
    |
    +-- connect.favorite

res.partner <-- (extended with connect fields)
res.users   <-- (extended with connect_user link)
mail.message <-- (extended with connect_message link)
```

### Twilio Extensions

```
connect.twiml (NEW - 100% Twilio)
    |
    +-- Used by: connect.domain, connect.user, connect.number

connect.domain (NEW - 100% Twilio)
    |
    +-- Used by: connect.user (SIP domain)

connect.whatsapp_sender (NEW - 100% Twilio)
    |
    +-- Used by: connect.user, whatsapp_composer wizard

connect.message_content_template (NEW - 100% Twilio)
    |
    +-- Used by: whatsapp_composer wizard
```

---

## Settings Architecture

The settings form uses a notebook widget with tabs. Core provides the base tabs,
and each integration module adds its own tab via view inheritance.

```
Settings Form (notebook)
  |
  +-- [Core] General tab
  |     - debug_mode, number_search_operation, proxy_recordings
  |
  +-- [Core] Registration tab
  |     - customer_code, registration fields, agree checkboxes
  |
  +-- [Core] Transcription tab
  |     - transcript_calls, transcript_provider, openai_api_key
  |     - summary_prompt, register_summary
  |
  +-- [Twilio] Twilio tab (added by connect_twilio)
  |     - account_sid, auth_token, api_key, api_secret
  |     - region, edge, auto_sync, verify_requests
  |     - balance display, sync buttons
  |     - fetch_call_prices
  |
  +-- [FreeSWITCH] FreeSWITCH tab (added by connect_freeswitch)
        - socket_url, domain
        - xmlrpc_host, xmlrpc_port, xmlrpc_user, xmlrpc_password
```

---

## Abstract Method Contracts

These methods are defined in core but must be implemented by at least one integration module:

### connect.message.send()

```python
def send(self):
    """Send the message via the telephony provider.

    Must:
    - Use from_number, to_number, body fields
    - Update status field on success/failure
    - Set error_code/error_message on failure
    - Set message_sid (or equivalent) on success
    """
    raise NotImplementedError
```

### connect.number.route_call()

```python
def route_call(self, params):
    """Route an incoming call to this number's destination.

    Must:
    - Check destination field (user/callflow/etc.)
    - Generate appropriate response for the provider
    - Return provider-specific response (TwiML, XML, etc.)
    """
    raise NotImplementedError
```

### connect.callflow.get_prompt_message() / get_gather_invalid_input_message() / get_voicemail_prompt_message()

```python
def get_prompt_message(self):
    """Return the prompt message for the caller.
    Override to add provider-specific text-to-speech or audio URL handling.
    """
    return self.prompt_message
```

### connect.user.on_call_action()

```python
def on_call_action(self, params):
    """Handle an incoming call action for this user.

    Must:
    - Process the call based on user's callflow configuration
    - Generate appropriate response
    """
    raise NotImplementedError
```

---

## Data Flow Examples

### Incoming Call (Twilio)

```
1. Twilio sends POST to /twilio/webhook/number/<id>/voice
2. twilio_webhooks.py validates signature, delegates to connect.number.route_call()
3. connect_twilio's route_call() checks destination:
   - user: calls connect.user.render() (Twilio override generates TwiML)
   - callflow: calls connect.callflow.render() (Twilio override generates TwiML)
   - twiml: calls connect.twiml.render()
4. TwiML response sent back to Twilio
5. Twilio sends status callbacks to /twilio/webhook/call/status
6. connect_twilio's on_call_status() creates/updates connect.channel and connect.call
7. Core's register_call() posts to partner chatter
```

### Recording Transcription

```
1. Integration module (Twilio/FreeSWITCH) creates connect.recording record
2. Core's recording.create() checks settings.transcript_calls
3. If enabled, calls core's transcribe_recording():
   a. Downloads audio from media_url (may be proxied)
   b. Calls OpenAI Whisper API via settings.get_openai_client()
   c. Stores transcript text
4. If transcript exists, calls core's make_summary():
   a. Calls OpenAI GPT-4o with summary_prompt from settings
   b. Stores summary HTML
5. Core's _sync_summary() posts summary to call's chatter
```

### SMS Send (via Composer)

```
1. User opens SMS composer (core wizard: sms_composer.py)
2. User selects outgoing number, enters message
3. Composer calls _action_send_sms()
4. _action_send_sms() creates connect.message record
5. Calls self.env['connect.message'].send()
6. connect_twilio's send() override:
   a. Gets Twilio client via settings.get_client()
   b. Calls client.messages.create()
   c. Updates message status and message_sid
```

---

## Module File Structure

```
connect/                              # Core (technology-agnostic)
  __init__.py
  __manifest__.py
  models/
    __init__.py
    settings.py                       # Singleton, OpenAI client, registration
    call.py                           # Call tracking, chatter
    channel.py                        # Call legs
    message.py                        # Messages (no send)
    recording.py                      # Recordings + OpenAI transcription
    user.py                           # PBX user profile
    user_callflow.py                  # User callflow config
    endpoint.py                       # Generic endpoint
    number.py                         # Inbound DIDs
    outgoing_callerid.py              # Outbound caller IDs
    exten.py                          # Extension routing
    callflow.py                       # IVR config (no rendering)
    callflow_choice.py                # IVR choices
    debug.py                          # Debug log
    res_partner.py                    # Partner extensions
    res_users.py                      # User extensions
    mail.py                           # Mail extensions
    message_configuration.py          # Message routing
    favorite.py                       # Favorites
  controllers/
    __init__.py
    main.py                           # Recording proxy, health check
  wizard/
    __init__.py
    transfer.py                       # Transfer wizard
    sms_composer.py                   # SMS composer (abstract send)
  security/
    groups.xml
    access_rules.xml
    record_rules.xml
  views/
    (all core model views)
    menu.xml
  data/
    data.xml
    res_users.xml
    ir_cron.xml

connect_twilio/                       # Twilio integration
  __init__.py
  __manifest__.py
  models/
    __init__.py
    settings.py                       # _inherit + Twilio credentials, client
    call.py                           # _inherit + CallSid, price, webhooks
    channel.py                        # _inherit + sid, notify
    message.py                        # _inherit + send/receive via Twilio
    recording.py                      # _inherit + Twilio SIDs, webhooks
    user.py                           # _inherit + SIP, client, TwiML
    number.py                         # _inherit + sync, webhook URLs
    outgoing_callerid.py              # _inherit + validation, sync
    callflow.py                       # _inherit + TwiML Gather
    twiml.py                          # NEW: TwiML apps
    domain.py                         # NEW: SIP domains
    whatsapp_sender.py                # NEW: WhatsApp senders
    message_content_template.py       # NEW: WhatsApp templates
  controllers/
    __init__.py
    twilio_webhooks.py                # All /twilio/webhook/* routes
  wizard/
    __init__.py
    whatsapp_composer.py              # WhatsApp composer
  security/
    groups.xml
    access_rules.xml
    record_rules.xml
  views/
    (Twilio-specific views + inherited extensions)
  data/
    twiml.xml
    whatsapp_templates.xml
  static/src/
    components/phone/                 # Phone UI (Twilio Voice SDK)
    js/main.js                        # Twilio Device init
    js/utils.js
    widgets/phone_field/              # Click-to-call
    services/                         # Active calls, mail extensions

connect_freeswitch/                   # FreeSWITCH integration (existing)
  (follows same _inherit pattern)
  models/
    fs_parking_slot.py                # connect.freeswitch.parking.slot
    call.py                           # _inherit; adds fs_parked_slot + Park actions
  controllers/
    freeswitch_parking.py             # GET /freeswitch/webhook/parking?event=…
  static/src/
    js/parking_panel.js               # OWL component for the Verto Parking tab
    xml/parking_panel.xml             # template
```
