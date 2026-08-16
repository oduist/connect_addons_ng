# Connect Architecture Specification

## Design Principles

1. **Core `connect` is technology-agnostic.** It holds the call/message ledger
   (call, channel, recording, message), the people directory (`connect.user`),
   transcription and common settings, provides UI, handles chatter integration,
   and defines provider-neutral hooks. It never imports `twilio`, never references
   Twilio-specific concepts (SIDs, TwiML, etc.), and never imports FreeSWITCH-specific code.

2. **PBX configuration models are fully owned per provider (ADR-031).** Extensions,
   call flows, numbers, endpoints and outgoing caller IDs are **independent models in
   the provider modules** (`connect.twilio.*`, `connect.freeswitch.*`,
   `connect.asterisk.*`) — not shared core models. Each telephony system lives in its
   own numbering plan; there is no call path between providers. The shared code these
   models carry (exten dst-Reference mechanics, callflow language list, E.164
   caller-ID constraint) is **duplicated on purpose — no mixins** (owner decision):
   fixes to those areas must be applied in `connect_twilio`,
   `connect_freeswitch` AND `connect_telnyx`.

3. **Integration modules still extend core models via `_inherit`.** Modules like
   `connect_twilio`, `connect_freeswitch`, `connect_asterisk`, `connect_telnyx`,
   `connect_infobip`, `connect_bird` and `connect_3cx` add adapter fields,
   methods, and webhook handlers to the shared core models (`connect.call`,
   `connect.channel`, `connect.user`, `connect.settings`). They never redefine
   core models. A provider module may own **no** PBX configuration models at
   all: `connect_3cx` (ADR-034) is settings + user + channel `_inherit` plus
   webhook controllers only — 3CX owns its numbering, routing and devices.

4. **OpenAI transcription is in core (not Twilio-specific).** Recording transcription via
   OpenAI Whisper and call summarization via a configurable OpenAI model are
   technology-agnostic features.
   Any telephony provider can produce a recording; any recording can be transcribed.
   The `openai` Python package is a core dependency, and `openai_api_key` +
   `get_openai_client()` live in `connect.settings`.

5. **SMS composers live in the messaging provider modules.** Both `connect_twilio`
   and `connect_bird` inherit `sms.composer`; sending goes through the core
   `connect.message.send()` **dispatcher** (ADR-035): core resolves the messaging
   provider per user via `connect.user.message_provider`
   (`connect.settings._get_message_provider()`, single-installed-provider
   fallback), each provider's `send()` override handles its own key and falls
   through to `super()` — the exact mirror of the click-to-call
   `originate_provider` machinery.

6. **Each integration module implements:** webhook handlers, API client initialization,
   protocol-specific rendering (TwiML, FreeSWITCH XML, etc.), provider-specific
   synchronization, and provider credential management.

7. **Webhook user is in core.** The special `connect.user_connect_webhook` res.users record
   is defined in core data. All integration modules use it when processing webhook callbacks
   to create/update records with proper permissions.

8. **`connect.settings` is one model with per-provider settings forms.** The settings
   singleton stays a single model, but each provider ships its **own standalone form
   view + menu entry** (Twilio → Configuration → Settings, etc.) instead of injecting
   notebook pages into the core form. The core `open_settings_form(view_xmlid, name)`
   action is parametrized so every module opens the same record through its own view.

---

## Extension Pattern

Two complementary patterns coexist since ADR-031:

**1. Shared ledger models — extended via `_inherit`.** Core holds the
call/message ledger + `connect.user` + `connect.settings`; provider modules
add adapter fields/methods and webhook handlers:

```
Core model (connect/models/call.py):
    _name = 'connect.call'

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


Integration model (connect_twilio/models/call.py):
    _inherit = 'connect.call'

    # Provider adapter fields
    call_sid = fields.Char(string='Call SID')

    # Provider-specific methods
    def on_call_status(self, params):
        """Twilio webhook handler"""
        ...
```

**2. PBX configuration models — owned by the provider module.** Extensions,
numbers, call flows, endpoints and caller IDs are independent `_name` models
per provider; core does not define them at all:

```
connect_twilio/models/number.py:
    _name = 'connect.twilio.number'      # full model, no core counterpart

connect_freeswitch/models/number.py:
    _name = 'connect.freeswitch.number'  # deliberate copy, no shared mixin
```

Cross-provider dispatch happens on the shared models: `connect.user` exposes
provider-neutral hooks (`_pbx_number_fields()` / `get_pbx_number()`, the
`originate_provider` Selection) that each provider module contributes to, and
`connect.settings.originate_call()` dispatches click-to-call to the provider
chosen on the user (implicit when exactly one provider is installed).

---

## Key Boundaries

### What lives in Core (`connect`)

| Category | Examples |
|----------|---------|
| Data models | call, channel, message, recording, user (the shared call/message ledger + people) |
| Computed fields | duration_human, recording_widget, direction_display |
| Chatter integration | register_call(), register_summary_to_rec() |
| Phone number handling | phonenumbers library, strip_number(), format_number() |
| Partner integration | get_partner_by_number(), create_record_from_message() |
| OpenAI transcription | transcribe_recording(), make_summary(), get_openai_client() |
| Provider-neutral hooks | connect.user._pbx_number_fields()/get_pbx_number(), originate_provider Selection, connect.settings.originate_call() dispatcher |
| Recording proxy | _serve_media() controller (abstract auth) |
| Security groups | group_user, group_admin, group_webhook |
| Webhook user | connect.user_connect_webhook |
| UI views | Ledger views, Users, the **Connect** app menu |
| Settings | Registration, usage tracking, OpenAI config; parametrized open_settings_form() |

### What lives in Integration Modules (`connect_twilio`, `connect_freeswitch`, `connect_asterisk`, `connect_telnyx`, `connect_infobip`, `connect_bird`, `connect_3cx`)

| Category | Examples |
|----------|---------|
| PBX configuration models | connect.twilio.{exten,callflow,number,outgoing_callerid,user_callflow,message_configuration}, connect.freeswitch.{exten,callflow,number,endpoint,outgoing_callerid}, connect.asterisk.{endpoint,number}, connect.telnyx.{exten,callflow,number,outgoing_callerid,user_callflow,message_configuration}, connect.bird.{number,message_template,message_configuration,webhook} — independent per-provider models, code duplicated on purpose (no mixins, ADR-031). `connect_3cx` owns none (ADR-034) |
| API client | get_client() for Twilio REST / freeswitch_api() for FreeSWITCH XML-RPC / asterisk_ami_action() via the sidecar agent / bird_request() raw HTTP helper / threecx_agent_request() via the 3CX sidecar agent |
| Webhook handlers | on_call_status(), receive(), on_recording_status(), on_ami_* adapters, receive_bird()/on_bird_call_event(), /3cx/webhook/* CRM-template handlers (lookup, report_call, create_contact) + on_threecx_participant_event agent events |
| Protocol rendering | TwiML generation, FreeSWITCH XML dialplan, Asterisk pjsip/manager.conf snippets, TeXML generation (connect_telnyx own builder) |
| Provider sync | sync() methods for numbers, callerIDs, domains, Bird numbers/templates |
| Credential management | SIP accounts, API keys, JWT tokens |
| Provider-specific models | connect.twilio.twiml, connect.twilio.domain, connect.whatsapp_sender, connect.firewall.{whitelist,blacklist,event,agent}, connect.asterisk.template, connect.telnyx.texml, connect.telnyx.domain |
| SMS composition | sms.composer inherits in the messaging provider modules; sending goes through the core connect.message.send() dispatcher (per-user message_provider), so co-installation is deterministic |
| Frontend SDK | Twilio Voice SDK phone widget, Verto WebRTC client, JsSIP web phone, Telnyx WebRTC phone widget. `connect_3cx` ships no phone: 3CX exposes no third-party WebRTC/WSS access — click-to-call opens the 3CX Web Client dial URL or originates via the sidecar agent (ADR-034/035) |
| Auxiliary services | `connect_freeswitch` ships a paired SIP-firewall service (own Docker image, talks ESL + iptables on the host kernel, see ADR-014). The service authenticates to Odoo via dedicated `/freeswitch/firewall/api/*` HTTP controllers carrying the shared `firewall_service_token` as `Authorization: Bearer …` — no dedicated Odoo user (ADR-015). `connect_asterisk` ships a thin sidecar agent (`oduist/asterisk-agent`) holding the persistent AMI connection to the customer's existing Asterisk; events flow to `/asterisk/webhook/*` and actions flow back over the agent HTTP API, both directions carrying the shared `asterisk_agent_token` as Bearer (ADR-026). |
| Message sending | send() implementation via provider API |
| Provider-specific fields | SIDs, webhook URLs, provider-specific status codes |

### Explicit Boundary Rules

1. **Core NEVER imports `twilio`** or any Twilio-specific Python package.
2. **Core NEVER imports FreeSWITCH- or Asterisk-specific** code (ESL libraries,
   AMI clients, agent HTTP protocols).
3. **Message send/receive** is split: core stores messages; integration modules
   implement `send()` and `receive()` webhook handlers (the composer UI lives in
   `connect_twilio`).
4. **Webhook handlers** for calls, recordings, and messages are 100% in integration modules.
5. **Recording proxy** (`_serve_media`) has its routing structure in core, but uses
   abstract auth that the integration module overrides (e.g., Twilio basic auth with
   account_sid/auth_token).
6. **SIP credential management** (create/update/delete SIP accounts) is 100% in the
   integration module.
7. **Call routing and callflow/IVR rendering** are entirely provider-owned: each
   provider module stores its own routing config (`connect.<provider>.number`,
   `connect.<provider>.callflow`) and renders to its protocol (TwiML for Twilio,
   XML dialplan for FreeSWITCH). Core has no routing models.
8. **Click-to-call is dispatched by core.** `connect.settings.originate_call()`
   resolves the provider from `connect.user.originate_provider` (implicit with a
   single installed provider); provider overrides chain via `super()`.
9. **Core models never reference provider models.** All Many2one/One2many fields
   pointing at `connect.<provider>.*` models are contributed by the provider module
   itself (e.g. `twilio_exten`, `freeswitch_endpoint_ids` on `connect.user`).

---

## Model Dependency Graph

```
connect.settings (singleton — one model, per-provider settings form views)
    |
    +-- connect.user (PBX users; provider-neutral hooks + originate_provider)
    |
    +-- connect.call
    |       |
    |       +-- connect.channel (call legs — shared ledger, all providers write here)
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
    |
    +-- connect.schedule (working hours on resource.calendar, ADR-037)
            |
            +-- connect.schedule.special_day (M2M)
            |
            +-- connect.schedule.slot (materialized availability calendar)

res.partner <-- (extended with connect fields)
res.users   <-- (extended with connect_user link)
mail.message <-- (extended with connect_message link)
```

PBX configuration models live per provider (no core counterparts):

### Twilio models (`connect_twilio`)

```
connect.twilio.exten (extension routing; dst Reference → connect.user /
    connect.twilio.callflow / connect.twilio.twiml)
connect.twilio.callflow (+ connect.twilio.callflow_choice) — IVR + TwiML Gather
connect.twilio.number (inbound DIDs, sync, webhook URLs)
    |
    +-- connect.twilio.message_configuration
connect.twilio.outgoing_callerid (outbound caller IDs, validation)
connect.twilio.user_callflow (+ connect.twilio.user_callflow_call)
connect.twilio.twiml (renamed from connect.twiml — TwiML apps)
connect.twilio.domain (renamed from connect.domain — SIP domains)
connect.whatsapp_sender — used by connect.user, whatsapp_composer wizard
connect.message_content_template — used by whatsapp_composer wizard

connect.user gains: twilio_exten, twilio_exten_number, twilio_outgoing_callerid,
username, domain, sip/client settings; originate_provider += 'twilio'
```

### FreeSWITCH models (`connect_freeswitch`)

```
connect.freeswitch.exten
connect.freeswitch.callflow (+ connect.freeswitch.callflow_choice)
connect.freeswitch.number
connect.freeswitch.endpoint (SIP devices)
connect.freeswitch.outgoing_callerid
connect.freeswitch.gateway / .outgoing_route / .template
connect.fs_fifo, connect.freeswitch.parking.slot
connect.firewall.{whitelist,blacklist,event,agent}

connect.user gains: freeswitch_exten, freeswitch_exten_number,
freeswitch_outgoing_callerid, freeswitch_endpoint_ids, webrtc fields;
originate_provider += 'freeswitch'

connect.freeswitch.number gains (ADR-037): schedule_enabled, schedule_id
(→ connect.schedule), closed_* after-hours destination fields,
schedule_prompt_language. connect_freeswitch_website (separate module,
depends website) adds the public snippets/endpoints on top.
```

### Asterisk models (`connect_asterisk`)

```
connect.asterisk.endpoint (standalone model — dial strings, SIP credentials)
connect.asterisk.number (minimal DID → user map for dialplan assist)
connect.asterisk.template (config snippets)

connect.user gains: asterisk_exten_number (plain Char — numbering stays in the
customer's dialplan), web phone preferences; originate_provider += 'asterisk'
```

### Telnyx models (`connect_telnyx`, ADR-032)

```
connect.telnyx.exten (+ dst Reference to user/callflow/texml)
connect.telnyx.callflow (+ connect.telnyx.callflow_choice)
connect.telnyx.number (attached to the routing TeXML app + messaging profile)
connect.telnyx.outgoing_callerid (owned numbers only — no validation API)
connect.telnyx.user_callflow (+ _call)
connect.telnyx.message_configuration
connect.telnyx.texml (TeXML application; Twilio-compatible XML, own builder)
connect.telnyx.domain (credential connection + TeXML app SIP subdomain)

connect.user gains: telnyx_exten(_number), telnyx_outgoing_callerid,
telnyx_domain, telnyx_{sip,client}_{enabled,priority,ring_timeout},
per-channel telephony credentials (sip_username/sip_password generated by
Telnyx); originate_provider += 'telnyx'
```

### Bird models (`connect_bird`, ADR-038)

```
connect.bird.number (synced sender identity registry — every send and
originate carries a `from` out of it)
connect.bird.message_template (approved SMS + WhatsApp templates)
connect.bird.message_configuration (inbound message routing)
connect.bird.webhook (webhook endpoint registry)

connect.user gains: bird_phone_number (agent phone for the two-leg callback
originate — Bird has no WebRTC SDK, so no web phone), bird_voice_number,
bird_message_number; originate_provider += 'bird'; message_provider += 'bird'
```

---

## Settings Architecture

`connect.settings` remains **one singleton model** — all provider fields live on
it — but every module ships its **own standalone form view and menu entry**
instead of injecting notebook pages into the core form (ADR-031). The core
action `connect.settings.open_settings_form(view_xmlid, name)` is parametrized:
each menu opens the same singleton record through the module's own view.

```
Connect > Configuration > Settings      → core view (general, registration,
                                          transcription/OpenAI)
Twilio > Configuration > Settings       → connect_twilio view (account_sid,
                                          auth_token, API keys, region/edge,
                                          sync, balance, fetch_call_prices)
FreeSWITCH > Configuration > Settings   → connect_freeswitch view (XML-RPC,
                                          domain, webhook token, firewall)
Asterisk > Configuration > Settings     → connect_asterisk view (agent URL/token,
                                          AMI bootstrap, web phone)
Telnyx > Configuration > Settings       → connect_telnyx view (API key, public
                                          key, account SID, sync, balance)
Bird > Configuration > Settings         → connect_bird view (access key,
                                          webhook setup, SMS category, ring
                                          timeout, signature verification)
```

Co-installation of several providers in one database is supported: Twilio's
`username`/`domain` on `connect.user` are enforced by a constraint only when the
Twilio SIP or web phone is enabled (not field-level `required`), and Twilio's
`client_enabled` defaults to True only when Twilio is the sole telephony module.

---

## Abstract Method Contracts

These methods are defined in core but implemented (or contributed to) by the
integration modules. Call routing and IVR rendering are **not** core contracts
anymore — the provider modules own those models entirely (ADR-031).

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

### connect.settings.originate_call()

```python
@api.model
def originate_call(self, number, res_model=None, res_id=None, user=None, **kwargs):
    """Dispatch click-to-call to the telephony provider chosen on the
    connect.user (originate_provider). With a single provider module
    installed the choice is implicit. Provider modules override this
    method: handle the call when the resolved provider key matches,
    otherwise fall through to super(). The core base raises a clear
    UserError when no provider can handle the call.
    """
```

### connect.user provider hooks

```python
@api.model
def _pbx_number_fields(self):
    """Names of Char fields on connect.user holding a provider extension
    number. Provider modules append their field (e.g. 'twilio_exten_number',
    'freeswitch_exten_number', 'asterisk_exten_number')."""
    return []

def get_pbx_number(self):
    """First non-empty provider extension number of this user."""

def get_user_by_uri(self, userinfo):
    """No-op in core (empty recordset). Providers override to map a
    SIP/client URI to a connect.user."""
```

`get_user_by_exten_number()` searches across all `_pbx_number_fields()`, so it
works with any combination of installed providers.

---

## Data Flow Examples

### Incoming Call (Twilio)

```
1. Twilio sends POST to /twilio/webhook/number/<id>/voice
2. twilio_webhooks.py validates signature, delegates to connect.twilio.number.route_call()
3. route_call() checks destination:
   - user: calls connect.user.render() (Twilio adapter generates TwiML)
   - callflow: calls connect.twilio.callflow.render()
   - twiml: calls connect.twilio.twiml.render()
4. TwiML response sent back to Twilio
5. Twilio sends status callbacks to /twilio/webhook/call/status
6. connect_twilio's on_call_status() creates/updates connect.channel and connect.call
7. Core's register_call() posts to partner chatter
```

### Recording Transcription

```
1. Integration module (Twilio/FreeSWITCH) creates connect.recording record
2. Core's recording.create() checks settings.transcript_calls
3. If enabled, marks the recording pending for the transcription cron
4. The cron calls core's transcribe_recording():
   a. Downloads audio from media_url (may be proxied)
   b. Calls OpenAI Whisper API via settings.get_openai_client()
   c. Stores transcript text on the recording and linked call
5. If transcript exists, calls core's make_summary():
   a. Calls the OpenAI summary model selected in settings (GPT-5.4 mini by default)
      with summary_prompt
   b. Stores summary HTML on the recording and linked call
6. If delete_recording_after_transcription is enabled and processing succeeded,
   core deletes the recording row after the call analysis is durable
7. The call summary registration constraints post the summary to configured
   business-record chatter targets
```

### SMS Send (via Composer)

```
1. User opens SMS composer (connect_twilio wizard: sms_composer.py,
   inherits sms.composer)
2. User selects outgoing number (from connect.twilio.number), enters message
3. Composer calls _action_send_sms()
4. _action_send_sms() creates connect.message record
5. Calls self.env['connect.message'].send()
6. connect_twilio's send() implementation:
   a. Gets Twilio client via settings.get_client()
   b. Calls client.messages.create()
   c. Updates message status and message_sid
```

### Click-to-call (any provider)

```
1. User clicks a phone number (phone_field widget / connect.call.redial)
2. Frontend calls connect.settings.originate_call(number, res_model, res_id)
3. Core resolves the provider: connect.user.originate_provider, or the only
   installed provider, or UserError
4. The matching provider override runs (Twilio API call / FreeSWITCH XML-RPC
   originate / AMI Originate through the Asterisk agent); non-matching
   overrides fall through via super()
```

---

## Module File Structure

```
connect/                              # Core (technology-agnostic ledger)
  __init__.py
  __manifest__.py
  models/
    __init__.py
    settings.py                       # Singleton, OpenAI client, registration,
                                      # originate_call() dispatcher
    call.py                           # Call tracking, chatter
    channel.py                        # Call legs (shared by all providers)
    message.py                        # Messages (no send)
    recording.py                      # Recordings + OpenAI transcription
    user.py                           # PBX user profile + provider hooks
    debug.py                          # Debug log
    res_partner.py                    # Partner extensions
    res_users.py                      # User extensions
    mail.py                           # Mail extensions
    favorite.py                       # Favorites
    license.py                        # License
  controllers/
    __init__.py
    main.py                           # Recording proxy, health check
  wizard/
    __init__.py
    transfer.py                       # Transfer wizard
  security/
    groups.xml
    access_rules.xml
    record_rules.xml
  views/
    (ledger + user + settings views)
    menu.xml                          # Connect app menu
  data/
    data.xml
    res_users.xml
    ir_cron.xml
  migrations/19.0.4.0.0/
    pre-migration.py                  # archive moved PBX tables as _*_legacy
  static/src/
    components/license_banner/        # License banner systray
    components/calls/                 # Shared Calls history widget (Calls tab,
                                      # imported by every provider phone panel)
    services/active_calls/            # Shared active-calls systray widget
                                      # (registered once, gated on group_user)

connect_twilio/                       # Twilio integration
  __init__.py
  __manifest__.py
  models/
    __init__.py
    settings.py                       # _inherit + Twilio credentials, client,
                                      # originate_call() override
    call.py                           # _inherit + CallSid, price, webhooks
    channel.py                        # _inherit + sid, notify
    message.py                        # _inherit + send/receive via Twilio
    recording.py                      # _inherit + Twilio SIDs, webhooks
    user.py                           # _inherit + SIP/client, twilio_exten,
                                      # co-install constraint
    exten.py                          # connect.twilio.exten
    callflow.py                       # connect.twilio.callflow (+_choice)
    number.py                         # connect.twilio.number
    outgoing_callerid.py              # connect.twilio.outgoing_callerid
    user_callflow.py                  # connect.twilio.user_callflow (+_call)
    message_configuration.py          # connect.twilio.message_configuration
    twiml.py                          # connect.twilio.twiml (TwiML apps)
    domain.py                         # connect.twilio.domain (SIP domains)
    whatsapp_sender.py                # WhatsApp senders
    message_content_template.py       # WhatsApp templates
  controllers/
    __init__.py
    twilio_webhooks.py                # All /twilio/webhook/* routes
  wizard/
    __init__.py
    sms_composer.py                   # SMS composer (sms.composer inherit)
    whatsapp_composer.py              # WhatsApp composer
  security/
    access_rules.xml
    record_rules.xml
  views/
    (Twilio model views, standalone settings view, Twilio app menu)
  data/
    twiml.xml
    whatsapp_templates.xml
  static/src/
    components/phone/                 # Phone UI (Twilio Voice SDK); Calls tab
                                      # imported from core connect
    js/main.js                        # Twilio Device init
    js/utils.js
    widgets/phone_field/              # Click-to-call
    services/                         # Actions, mail extensions
                                      # (active-calls widget now in core)

connect_freeswitch/                   # FreeSWITCH integration
  models/
    exten.py                          # connect.freeswitch.exten
    fs_callflow.py                    # connect.freeswitch.callflow (+_choice)
    number.py                         # connect.freeswitch.number
    endpoint.py                       # connect.freeswitch.endpoint
    outgoing_callerid.py              # connect.freeswitch.outgoing_callerid
    gateway.py / outgoing_route.py / fs_template.py
    fs_fifo.py                        # connect.fs_fifo
    fs_parking_slot.py                # connect.freeswitch.parking.slot
    firewall.py                       # connect.firewall.*
    fs_user.py                        # _inherit connect.user (WebRTC, exten)
    call.py / settings.py             # _inherit (originate, XML-RPC)
  controllers/
    freeswitch_xml.py / freeswitch_cdr.py / freeswitch_parking.py / firewall_api.py
  migrations/19.0.2.0.0/
    pre-migration.py                  # detach fifo FKs
    post-migration.py                 # id-preserving copy from _*_legacy tables
  static/src/                         # Verto client, parking panel

connect_asterisk/                     # Asterisk integration
  models/
    endpoint.py                       # connect.asterisk.endpoint (standalone)
    number.py                         # connect.asterisk.number (DID → user)
    ast_template.py                   # connect.asterisk.template
    user.py                           # _inherit (asterisk_exten_number, prefs)
    channel.py / recording.py / settings.py / res_users.py   # _inherit
  controllers/
    webhooks.py / agent_api.py
  deploy/agent/                       # oduist/asterisk-agent sidecar
  static/src/                         # JsSIP web phone

connect_telnyx/                       # Telnyx integration (TeXML-first, ADR-032)
  models/
    texml_response.py                 # own TeXML builder (no twilio dependency)
    texml.py                          # connect.telnyx.texml (TeXML apps)
    domain.py                         # credential connection + app SIP subdomain
    exten.py / callflow.py / number.py / outgoing_callerid.py
    user_callflow.py / message_configuration.py
    user.py / call.py / channel.py / message.py / recording.py / settings.py  # _inherit
  controllers/
    telnyx_webhooks.py                # /telnyx/webhook/* (Ed25519 validation)
  static/src/                         # @telnyx/webrtc phone widget

connect_bird/                         # Bird.com (MessageBird) integration
  models/
    bird_number.py                    # connect.bird.number (synced registry)
    message_template.py               # connect.bird.message_template
    message_configuration.py          # connect.bird.message_configuration
    bird_webhook.py                   # connect.bird.webhook (endpoint registry)
    user.py                           # _inherit (bird_phone_number, numbers)
    message.py / channel.py / call.py / recording.py / settings.py  # _inherit
  controllers/
    bird_webhooks.py                  # single /bird/webhook endpoint
  wizard/
    sms_composer.py / whatsapp_composer.py

connect_crm_twilio/                   # auto-installed bridge (connect_crm ×
                                      # connect_twilio): message_configuration
                                      # CRM extension
```

---

## Menu Structure

**Connect** is the single top-level app. Each provider module adds its own
submenu under it; all provider submenus share sequence 50, so they appear
after Calls/Users in installation order (equal sequence falls back to id
order), and the core Configuration menu (seq 100) always stays last.

```
Connect
  +-- Calls {Calls, Recordings, Channels (admin)}
  +-- Users
  +-- Twilio:      Numbers, Extensions, Call Flows, Outgoing Caller IDs,
  |                TwiML Apps, SIP Domains, Messages {Messages, Message
  |                Configuration (admin), WhatsApp Senders (admin), WhatsApp
  |                Templates (admin)}, Configuration {Settings}
  +-- FreeSWITCH:  Numbers, Extensions, Call Flows, Endpoints, Outgoing
  |                Caller IDs, FIFO Queues, Parking Slots, Firewall {Agent
  |                Status, Whitelist, Blacklist, Events}, Configuration
  |                {SIP Gateways, Outgoing Routes, XML Templates, Settings}
  +-- Asterisk:    Endpoints, Numbers, Configuration {Templates, Settings}
  +-- Bird:        Numbers, Messages {Messages}, Configuration {Settings,
  |                Message Templates, Message Configuration, Webhook
  |                Endpoints}
  +-- Configuration {Settings, Debug Log (admin), License}
```
