# Telnyx Integration Setup

## Prerequisites

- A Telnyx account ([telnyx.com](https://telnyx.com))
- An API key (Mission Control Portal > Account > Keys & Credentials)
- The account **Public Key** (same page) — used to verify webhook signatures
- The **TeXML Account SID** (your Telnyx account ID, shown in the TeXML section of the portal)
- At least one Telnyx phone number
- An **Outbound Voice Profile** (Voice > Outbound Voice Profiles) if you plan to place PSTN calls

## Account Configuration

Navigate to **Connect > Telnyx > Configuration > Settings**.

### Credentials

| Field | Description |
|-------|-------------|
| **API Key** | Your Telnyx v2 API key. Masked for non-managers. |
| **Public Key** | The Ed25519 public key from Mission Control. Not secret; required to verify webhook signatures. |
| **Account SID** | The TeXML Account SID (your Telnyx account ID). Required for click-to-call. |

### Options

| Field | Description |
|-------|-------------|
| **Auto Sync** | Automatically push changes to Telnyx when creating/updating records in Odoo. |
| **Verify Telnyx Requests** | Validate the `telnyx-signature-ed25519` header on incoming webhooks. Recommended for production. |
| **Fetch Call Prices** | Retrieve call cost from Telnyx detail records after each call completes (best effort). |

### Sync

Click **SYNC TELNYX ACCOUNT** to import and wire up Telnyx resources:

- TeXML applications (created for each Odoo TeXML app)
- SIP domains (credential connections + the routing TeXML app subdomain)
- Phone numbers (attached to the routing app and the messaging profile)
- Outgoing caller IDs (numbers owned in the account)

The sync also creates the **Odoo Connect** messaging profile with the
webhook URL pointing at your Odoo instance.

## Voice Routing

Telnyx voice is integrated through **TeXML** (the Twilio-compatible XML
translator):

1. Create a **SIP Domain** (Connect > Telnyx > SIP Domains). This creates
   a Telnyx *credential connection* (hosting per-user SIP credentials)
   and reserves a SIP subdomain (`<subdomain>.sip.telnyx.com`) on the
   routing TeXML application, so web-phone calls are routed by Odoo.
2. Assign inbound numbers (Connect > Telnyx > Numbers) to a user, a call
   flow or a TeXML app.
3. Enable the **Telnyx Phone** (SIP and/or Web) on users (Connect > Users
   > Telnyx Phone tab). Telnyx generates the SIP username and password —
   use them to provision a hardphone; the web phone authenticates with a
   short-lived token automatically.

### Webhooks

All webhooks are served under `/telnyx/webhook/*`. The public URL of the
Odoo instance must be set in the core Connect settings (`api_url`); the
TeXML application voice URLs are derived from it and pushed to Telnyx by
the sync.

Webhook authenticity is verified with the account's Ed25519 **Public
Key** (`telnyx-signature-ed25519` / `telnyx-timestamp` headers). Keep
**Verify Telnyx Requests** enabled in production.

## Messaging

SMS/MMS use the **Odoo Connect** messaging profile created by the sync.
Numbers synced from Telnyx are attached to it automatically. Incoming
messages and delivery reports arrive on `/telnyx/webhook/message` as
Telnyx v2 JSON events.

Message routing to Odoo records is configured under Connect > Telnyx >
Messages > Message Configuration.

## WhatsApp

Onboard your WhatsApp Business Account and phone numbers in the Telnyx
Mission Control Portal first, then run **SYNC TELNYX ACCOUNT** (or the
Sync button on the list views):

- **WhatsApp Senders** (Connect > Telnyx > Messages) are imported from
  the account's WhatsApp phone numbers. The business profile (about,
  address, description, email, website) is editable in Odoo and pushed
  back to Telnyx. Mark one sender as **Default**; users may also have a
  personal sender (Connect > Users > Telnyx WhatsApp Sender).
- **WhatsApp Templates** are synced with their Meta approval status.
  New templates (body text with `{{1}}`-style variables) can be created
  in Odoo and submitted for approval with one click.
- Sending: the WhatsApp **Message** button on phone fields, the
  *WhatsApp Reply* action on chatter messages, or the composer wizard.
  Freeform messages are allowed only within the 24-hour customer
  window; outside of it an approved template must be selected.
- Incoming WhatsApp messages and delivery reports arrive on the same
  `/telnyx/webhook/message` route (`payload.type = whatsapp`).

## RCS

RCS agents are provisioned through Telnyx (Google RBM verification) and
synced read-only into **RCS Agents** (Connect > Telnyx > Messages).
Sending uses the *RCS Reply* chatter action or the composer wizard;
messages are sent as RCS text with an optional SMS fallback from a
configurable sender number. Incoming RCS messages arrive as
`payload.type = RCS` on the messaging webhook.

## Known limitations (v1)

- WhatsApp voice calling is not integrated (messaging only); rich RCS
  cards/carousels are not composed from Odoo (text + SMS fallback only).
- Attended transfer from the web phone is not available yet.
- Call cost fetching relies on Telnyx detail records and may lag behind
  call completion.
- Outbound calls from SIP hardphones go directly through the credential
  connection (Telnyx handles them); internal extension dialing from
  hardphones is not routed by Odoo yet.
