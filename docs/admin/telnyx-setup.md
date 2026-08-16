# Telnyx Integration Setup

## Prerequisites

- A Telnyx account ([telnyx.com](https://telnyx.com))
- An API key (Mission Control Portal > Account > Keys & Credentials)
- The account **Public Key** (same page) — used to verify webhook signatures
- The **TeXML Account SID** — filled in automatically by the account sync; you
  only need it by hand if the sync cannot reach the API
- At least one Telnyx phone number
- An **Outbound Voice Profile** (Voice > Outbound Voice Profiles) if you plan to place PSTN calls

## Account Configuration

Navigate to **Connect > Telnyx > Configuration > Settings**.

## AI Voice Assistants

After the credentials and public HTTPS API URL are configured, open
**Connect > Telnyx > AI Assistants**. Creating a record creates the Telnyx AI
Assistant and configures its dynamic-variable and tool webhooks. **Pull from
Telnyx** refreshes a record; the main **SYNC TELNYX ACCOUNT** action also
imports assistants created in Mission Control.

To answer an existing Telnyx number with an assistant, open the number and set
**Destination** to **AI Assistant**. The number remains attached to the Odoo
TeXML routing application; do not assign it directly to the assistant in
Mission Control.

The **Call with Assistant** button starts an outbound call using an existing
owned caller ID. It never buys or assigns a number. Recording and memory are
off by default and must be enabled on each assistant. CRM and Helpdesk tools
are published only when the matching Connect modules are installed.

Telnyx signs context and insight callbacks with the account Ed25519 public
key. Odoo tools use a separate random token per assistant; rotate it from the
assistant form if it may have been exposed.

### Credentials

| Field | Description |
|-------|-------------|
| **API Key** | Your Telnyx v2 API key. Masked for non-managers. |
| **Public Key** | The Ed25519 public key from Mission Control. Not secret; required to verify webhook signatures. |
| **Account SID** | The TeXML Account SID (your Telnyx account ID). Required for click-to-call and filled in by the account sync. |

### Outbound destinations

Telnyx only places calls to the countries whitelisted on the account's
**outbound voice profile**, and a new profile ships allowing `US, CA` only.
A call to any other country is rejected by Telnyx *before* it reaches Odoo,
so a perfectly registered phone simply fails to dial.

The **Outbound Destinations** field on the settings form holds that list as
comma-separated ISO country codes (`PL, DE, US`); saving it writes straight
onto the profile. An empty value allows every destination. The account sync
reads the current list back and warns when a country of one of your own
numbers is missing from it.

### Options

| Field | Description |
|-------|-------------|
| **System Voice Language** | Language filter for the system voice catalog. Default: English (United States). |
| **System Voice Provider** | Provider filter for the system voice catalog. Default: Amazon Web Services. |
| **System Voice** | Default TeXML `<Say>` voice, selected from voices matching the language and provider. Search by voice name, gender, or Telnyx ID. User and callflow voice overrides still win. Default: Joanna (`Polly.Joanna`). |
| **Auto Sync** | Automatically push changes to Telnyx when creating/updating records in Odoo. |
| **Verify Telnyx Requests** | Validate the `telnyx-signature-ed25519` header on incoming webhooks. Recommended for production. |
| **Fetch Call Prices** | Retrieve call cost from Telnyx detail records after each call completes (best effort). |

The voice catalog comes from Telnyx `GET /v2/text-to-speech/voices`, so it can
include Telnyx voices, supported third-party providers, and cloned voices
available to the account. Select a language and provider first; **System
Voice** then searches only that matching subset and displays readable voice
names with gender and the underlying Telnyx ID. Click **REFRESH VOICES** after
adding a voice in Voice Design Lab. The normal **SYNC TELNYX ACCOUNT** action
refreshes the same catalog. If the catalog cannot be fetched, the current
selection and the basic TeXML voices remain available.

### Sync

Click **SYNC TELNYX ACCOUNT** to import and wire up Telnyx resources:

- TeXML applications (created for each Odoo TeXML app)
- SIP domains (credential connections + the routing TeXML app subdomain)
- Phone numbers (attached to the **Number Calls** application and, when the
  number supports SMS, to the messaging profile)
- Outgoing caller IDs (numbers owned in the account)

A number without SMS capability cannot join the messaging profile; the sync
logs that and continues, since the number still works for voice.

The sync also creates the **Odoo Connect** messaging profile with the
webhook URL pointing at your Odoo instance.

If an optional WhatsApp/RCS resource or an imported AI Assistant cannot be
synchronized, Odoo shows a persistent warning. The warning remains visible
until it is dismissed so the API error can be reviewed and corrected.

## Voice Routing

Telnyx voice is integrated through **TeXML** (the Twilio-compatible XML
translator):

Before returning TeXML, Odoo adds **System Voice** to every `<Say>` that does
not already carry `voice`. This also covers routing/service notices, custom
TeXML, TeXPy, and nested `<Say>` nodes inside `<Gather>`. An explicit voice on
a user prompt, callflow prompt, or custom `<Say>` is preserved.

1. Create a **SIP Domain** (Connect > Telnyx > SIP Domains). This creates
   a Telnyx *credential connection* (hosting per-user SIP credentials)
   and reserves a SIP subdomain (`<subdomain>.sip.telnyx.com`) on the
   routing TeXML application, so web-phone calls are routed by Odoo. The
   connection is created with **SIP URI calling** set to *internal*:
   Odoo rings a phone at `sip:<credential>@sip.telnyx.com`, and Telnyx
   answers such a call with `403 Forbidden` while that setting is off.
   The subdomain is the inbound side only — ringing a credential there
   would hand the call back to the routing application instead of the
   phone. Telnyx may omit the `sip:` prefix from routing callbacks; Odoo
   accepts both callback forms and still rejects an actual credential loop.
2. Assign inbound numbers (Connect > Telnyx > Numbers) to a user, a call
   flow, a TeXML app or an AI assistant. Inbound calls to a number are
   dispatched by the dialled number; a number with no destination answers
   with a spoken notice instead of dialling anything.
3. Enable the **Telnyx Phone** (SIP and/or Web) on users (Connect > Users
   > Telnyx Phone tab). Telnyx generates the SIP username and password —
   use them to provision a hardphone; the web phone authenticates with a
   short-lived token automatically.
4. User destinations are tried in their configured priority order. Odoo
   advances to the next destination or voicemail only when Telnyx reports an
   explicit unsuccessful Dial result, such as busy or no answer. Once a SIP or
   web-phone destination was answered, ending that leg terminates the inbound
   call instead of starting voicemail.

### SIP username and password

Both are issued by Telnyx when the credential is created, and the API
accepts neither on create nor on update — **a password cannot be typed in
or changed in place**, which is why both fields are read-only in Odoo.

- **Reading them:** Connect > Users > *the user* > Telnyx Phone tab. Both
  fields are shown in the clear with a copy button, so they can be pasted
  straight into a hardphone. They are visible to the Connect User and
  Connect Admin groups.
- **Rotating them:** press **Regenerate SIP credential** (Connect Admin
  only). Odoo deletes the credential in Telnyx and asks for a new one, so
  the **username changes as well** and the hardphone must be configured
  again with both new values.
- The web phone is unaffected: it authenticates with a short-lived token
  fetched per session, not with these credentials.

### Webhooks

All webhooks are served under `/telnyx/webhook/*`. The public URL of the
Odoo instance must be set in the core Connect settings (`api_url`); the
TeXML application voice URLs are derived from it and pushed to Telnyx by
the sync.

Webhook authenticity is verified with the account's Ed25519 **Public
Key** (`telnyx-signature-ed25519` / `telnyx-timestamp` headers). Keep
**Verify Telnyx Requests** enabled in production. Telnyx signs the POST body
byte for byte, so a reverse proxy must forward the form body without decoding
and re-encoding it. If a Dial action signature is invalid, Odoo rejects it and
silently hangs up the remaining leg instead of playing an error message.

Recording callbacks may contain short-lived signed download URLs. Odoo keeps
the URL on the recording record for playback, but redacts it from Telnyx debug
payloads so temporary download credentials are not persisted in
`connect.debug`.

For outbound calls placed from the Telnyx web phone or a SIP credential, Odoo
applies the originating PBX user's **Record Calls** setting to the generated
TeXML `<Dial>`. Telnyx may identify that user in different webhook fields;
Odoo normalizes those variants before selecting the caller ID and recording
policy.

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
