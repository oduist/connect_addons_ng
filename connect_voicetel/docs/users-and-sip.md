# Users, SIP & Browser Phone

## SIP domains

**Connect ▸ VoiceTel ▸ SIP Domains** lists the tenant SIP domains. A domain
has a **Label** (a DNS label such as `acme`); its SIP domain is
`<label>.<suffix>` (for example `acme.vml.voice.tel`) and its WebSocket URL
`wss://acme.vml.voice.tel:8443`.

Creating a domain creates, on the VoiceML account:

- the **SIP Domain** itself, pointing at the **SIP Domain Calls** VoiceML
  app so that every call a registered device places is routed by Odoo;
- one **Credential List**, mapped to the domain for both registrations and
  calls.

A domain whose name is already held by the account is adopted rather than
duplicated. A name held by another tenant is refused.

Domains carry **delete protection**; deleting a domain removes its
credential list and mappings from the account.

## Per-user SIP account

Open a Connect user (**Connect ▸ Users**) and the **VoiceTel Phone** tab.

| Field | Description |
|-------|-------------|
| **Enabled** (SIP Account) | Creates a SIP credential in the domain's credential list. |
| **SIP Domain** | The domain the credential belongs to. Cannot change while the credential exists. |
| **Username** | Alphanumeric SIP username, unique across VoiceTel users. Cannot change while the credential exists. |
| **Password** | SIP digest password. Leave it empty to have one generated. It stays readable by the user and the administrator: the browser phone registers with it. |
| **Ring Timeout** | Seconds the user's devices ring before the call moves on (voicemail or the next ring-group member). |
| **SIP URI** | `username@label.suffix`, the address colleagues and call flows dial. |
| **VoiceML App** | Optional app used when a call this user places is routed (defaults to the domain's app). |

Every device registered with the credential rings at once: a desk phone,
the VoiceML Phone desktop or mobile app, and the browser phone share it. The
dialplan rings the user with one `<Dial><Sip>` noun on the tenant domain.

The **VoiceTel Extension** button in the header assigns an extension to the
user (see [Numbers & Call Routing](numbers-and-routing.md)).

## Browser phone

**Enabled** (Browser Phone) loads the web phone in the user's Odoo session.
It requires the SIP account and the global **Browser Phone** switch in the
settings. The phone registers over WSS to the user's SIP domain with the SIP
credential, exactly like the VoiceML Phone apps.

Per-user preferences: **Ring Volume**, **Mask Numbers** (hides the middle
digits of phone numbers in the phone), **Call Popup** and **Sticky Popup**.

Click-to-call from a `phone` field uses the browser phone when it is
registered; the call then reaches VoiceML through the registrar and is
routed by the SIP domain's app. Without a registered browser phone, Odoo
places the call through the REST API to the user's SIP URI and connects the
destination once the user answers (desk phone or VoiceML Phone app).

## Caller ID of a user

Calls a user places present, in this order: the user's **extension** (for
internal calls), the user's **Outgoing Caller ID**, the default outgoing
caller ID, and finally the SIP username. Set the user's outgoing caller ID on
the user form.

## Voicemail and greeting

The core **Voicemail** and **Greeting** fields apply: when the user's devices
do not answer, the voicemail prompt is played and the message recorded, then
stored on the call.
