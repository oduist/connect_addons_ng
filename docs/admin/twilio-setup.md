# Twilio Integration Setup

## Prerequisites

- A Twilio account ([twilio.com](https://www.twilio.com))
- Account SID and Auth Token (from Twilio Console > Account Info)
- API Key and API Secret (from Twilio Console > API Keys)
- At least one Twilio phone number

## Account Configuration

Navigate to **Connect > Twilio > Configuration > Settings**.

### Credentials

| Field | Description |
|-------|-------------|
| **Account SID** | Your Twilio Account SID (starts with `AC`). |
| **Auth Token** | Your Twilio Auth Token. Masked for non-managers. |
| **API Key** | Twilio API Key SID (starts with `SK`). Required for Voice SDK tokens. |
| **API Secret** | Twilio API Secret. Masked for non-managers. |

### Region and Edge

| Field | Description |
|-------|-------------|
| **Region** | Twilio data center region: US East (`us1`), Ireland (`ie1`), or Australia (`au1`). |
| **Edge** | Nearest Twilio edge server for latency optimization (e.g., ashburn, dublin, sydney). |

### Options

| Field | Description |
|-------|-------------|
| **Auto Sync** | Automatically push changes to Twilio when creating/updating records in Odoo. |
| **Verify Requests** | Validate `X-Twilio-Signature` header on incoming webhooks. Recommended for production. |
| **Fetch Call Prices** | Retrieve call cost from Twilio API after each call completes. |

### Sync

Click **SYNC TWILIO ACCOUNT** to import all Twilio resources:

- Phone numbers
- Outgoing caller IDs
- SIP domains
- TwiML applications
- WhatsApp senders

## SIP Domains

Navigate to **Connect > Twilio > SIP Domains** to manage SIP domains.

A SIP domain is required for SIP phone registration and the web phone widget.

| Field | Description |
|-------|-------------|
| **Subdomain** | Custom subdomain (e.g., `mycompany` creates `mycompany.sip.twilio.com`). |
| **Application** | TwiML app that handles voice for this domain. Auto-created if empty. |
| **SIP Registration** | Allow SIP phones to register. |
| **Delete Protection** | Prevent accidental deletion. |

When you create a domain, Connect automatically:

1. Creates the SIP domain on Twilio
2. Creates a credential list
3. Adds SIP credentials for all existing PBX users

## User Setup (Twilio-specific)

When editing a PBX user (**Connect > Users**), the Twilio integration adds:

### Phone Channels

| Field | Description |
|-------|-------------|
| **Web Phone Enabled** | Allow this user to make/receive calls from the browser. Enabled by default only when Twilio is the sole installed telephony module; with several providers installed, enable it explicitly per user. |
| **Web Phone Priority** | Ring order: 1 = first, 2 = second. |
| **Web Phone Ring Timeout** | Seconds to ring before moving to next channel. |
| **SIP Phone Enabled** | Allow this user to register a SIP phone. |
| **SIP Priority** | Ring order for SIP phone. |
| **SIP Ring Timeout** | Seconds to ring SIP phone. |

### SIP Credentials

| Field | Description |
|-------|-------------|
| **Username** | Alphanumeric PBX username (unique). Required only when the SIP phone or web phone is enabled — a user without Twilio phones can leave it empty (relevant when several provider modules are co-installed). |
| **Domain** | SIP domain for this user. Same conditional requirement as Username. |
| **Password** | SIP password. Auto-generated with strong policy (12+ chars). |
| **SIP URI** | Computed: `username@domain.sip.twilio.com`. |
| **Edge** | Preferred Twilio edge for this user. |

### Other

| Field | Description |
|-------|-------------|
| **TwiML Application** | Override domain-level TwiML app for this user. |
| **WhatsApp Sender** | WhatsApp number assigned to this user. |

### Extension

Give every PBX user an extension: open the user and press **Extension**, then
enter the number (100, 101, ...). The extension is what colleagues dial to
reach the user, and it is the caller ID the user's own calls present — the
number that shows on the callee's phone and in the call history.

A user without an extension still places calls, but presents their client
identity (`client:<username>@<domain>`) instead, so the call history shows the
login rather than a number. Assigning the extension corrects both.

## TwiML Applications

Navigate to **Connect > Twilio > TwiML Apps** to manage voice applications.

TwiML apps define custom call handling logic:

| Code Type | Description |
|-----------|-------------|
| **TwiML** | Raw TwiML XML with Jinja2 template support. |
| **TwiPy** | Python code that programmatically generates TwiML. |
| **Model Method** | Call an Odoo model method to generate TwiML. |

Each TwiML app can be assigned an extension number for direct dialing.

## Phone Numbers (Twilio-specific)

Navigate to **Connect > Twilio > Numbers**. In addition to the common number fields,
Twilio numbers carry:

| Field | Description |
|-------|-------------|
| **SID** | Twilio Phone Number SID. Populated by sync. |
| **Destination** | Includes **TwiML** as a routing option (in addition to User and Callflow). |
| **Ignore** | Skip this number during sync operations. |

Webhook URLs for voice and messaging are automatically configured when you assign a destination.

The destination also serves inbound **WhatsApp** calls to that number: a
WhatsApp call reaches the same user, callflow or TwiML app as a regular call,
with no extra setup. Create an extension for the number only when WhatsApp
should follow a different dialplan than the destination — an extension takes
precedence over it.

## WhatsApp Setup

### WhatsApp Senders

Navigate to **Connect > Twilio > Messages > WhatsApp Senders** to manage WhatsApp-enabled numbers.

Click **Sync** to import senders from your Twilio account.

| Field | Description |
|-------|-------------|
| **Number** | WhatsApp phone number. |
| **Status** | Online/Offline. |
| **Default** | Default sender for users without a personal sender assigned. |
| **Profile** | Business profile (name, about, address, description). |
| **Quality Rating** | Twilio quality rating. |
| **Messaging Limit** | Daily message limit. |
| **Voice Application** | TwiML app for WhatsApp voice calls. |

Only synchronized senders with status **Online** can be assigned to a user or
selected automatically for a new outgoing message or WhatsApp call. An offline
personal or default sender is skipped in favor of the next online sender.

### WhatsApp Message Templates

Navigate to **Connect > Twilio > Messages > WhatsApp Templates** to manage pre-approved message templates.

Templates must be approved by WhatsApp before they can be used for outbound messaging. Use **Sync** to import templates from Twilio.

| Field | Description |
|-------|-------------|
| **Name** | Template name. |
| **Category** | Utility, Authentication, or Marketing. |
| **Language** | Template language. |
| **Content Type** | Text, media, list-picker, card, carousel, etc. |
| **Variables** | Placeholder variables (`{{1}}`, `{{2}}`, etc.). |
| **Approval Status** | Unsubmitted, pending, approved, rejected, paused, disabled. |

## Webhook URL

Your Odoo instance must be accessible from the internet for Twilio webhooks. Set the **API URL** in **Connect > Configuration > Settings** to your public Odoo URL (e.g., `https://odoo.example.com`).

All Twilio webhooks are under `/twilio/webhook/*`.

## Outgoing Caller ID Validation

For Twilio, outgoing caller IDs can be validated:

1. Create a new caller ID in **Connect > Twilio > Outgoing Caller IDs**
2. Click **Validate** — Twilio will call the number and provide a validation code
3. Enter the validation code to confirm the number
