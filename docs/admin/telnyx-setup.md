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
Assistant and configures its dynamic-variable and tool webhooks. Odoo is the
source of truth: edit assistants in Odoo and use **Push to Telnyx** or account
sync. Assistants created only in Mission Control are not imported or changed.

To answer an existing Telnyx number with an assistant, open the number and set
**Destination** to **AI Assistant**. The number remains attached to the Odoo
TeXML routing application; do not assign it directly to the assistant in
Mission Control.

The **Call with Assistant** button starts an outbound call using an existing
owned caller ID. It never buys or assigns a number.

### Receptionist routing

Choose one receptionist mode on the assistant:

- **Personal Receptionist** answers for one manager. It qualifies the caller
  and can warm-transfer to that manager.
- **Company Receptionist** replaces an IVR. Select department callflows such
  as Sales, Quality, or Director; their configured ring users become the human
  transfer candidates.

Enable the manager's SIP phone and/or Web Phone and ensure Telnyx credentials
exist. With **Check Registration Before Transfer**, Odoo calls
`GET /v2/sip_registration_status` for each telephony credential. This endpoint
covers both SIP hardphones and Telnyx WebRTC SDK registrations. A registered
device is eligible for transfer, but registration does not guarantee that the
person will answer; busy, rejection, and no-answer remain possible. If the
status API itself fails, Odoo keeps a configured target as an advisory fallback.

The Telnyx shared Transfer tool dials the selected credential directly and
performs a warm transfer. Before bridging the caller, the assistant briefs the
recipient with the confirmed caller name, reason, relevant context, and agreed
next step. If no recipient is registered, the assistant offers to register the
request instead.

**Warm Transfer Message Delay** defaults to `2000` ms. It gives a newly
answered WebRTC call time to establish its media path before Telnyx plays the
private briefing. Treat this as a reversible compatibility setting: if a test
call still has silent briefing audio, or the delay only adds an unnecessary
pause, set it to `0` and use **Push to Telnyx**. Zero clears the delay and
restores the previous immediate-playback behavior.

While Telnyx privately briefs the recipient, the caller hears transfer
progress/ringback. The built-in Transfer tool does not provide caller-side
hold music. Adding music requires a separate custom Call Control or conference
transfer flow; it is not enabled by the delay setting.

To make the assistant callable without a public number, select a SIP domain
and click **Create Extension**. Registered SIP and WebRTC phones can then call
`sip:<extension>@<subdomain>.sip.telnyx.com` (or dial the extension through the
configured web phone).

### Caller identity and Odoo tools

At conversation start Odoo searches both phone and mobile numbers. The
assistant receives a caller name only when exactly one contact matches and
must ask the caller to confirm it. Duplicate matches are marked ambiguous and
no name is guessed.

### Languages and multilingual assistants

The assistant form separates the caller-language policy from speech
recognition:

- **Contact Language, Then Auto-Detect** starts with the language of the one
  contact matched by phone. If no unique contact language exists, it uses
  **Agent Language**. The assistant may follow a caller who clearly changes
  language.
- **Fixed Agent Language** ignores the contact language and does not switch.
- **Automatic Detection** greets in **Agent Language**, then follows the
  language detected from speech.

Activate the required languages in Odoo and set **Language** on each contact.
Odoo returns the normalized BCP-47 code, language name, and localized initial
greeting through the signed dynamic-variable webhook. Russian and Polish
translations of the standard receptionist greeting ship with the module;
other languages use the configured fallback greeting until their Odoo
translation is installed.

For multilingual speech recognition, use `deepgram/nova-3` with
**Transcription Language** set to `auto`; these are the defaults for new
assistants. Telnyx also supports multilingual alternatives such as
`deepgram/flux`, Azure, AssemblyAI, xAI, Soniox, and NVIDIA, with different
language coverage and turn-taking behavior.

Speech output is independent. `AWS.Polly.Joanna-Neural` is English-only, so
select Telnyx Ultra, Azure Multilingual, MiniMax, Inworld, or another voice
whose Telnyx catalog entry and provider documentation cover every required
language. A fixed-language transcription setting or single-language voice
intentionally limits the agent even when its LLM understands several
languages.

**Voice** is picked from the voices available to your Telnyx account, not
typed as an identifier. Choose **Voice Language** and **Voice Provider**
first — they only filter the catalog and are never sent to Telnyx — then
search the **Voice** field by name, gender, or Telnyx ID. Cloned and designed
voices appear under their own name, so an assistant shows *Callie* rather than
`Telnyx.Ultra.00a77add-…`. Both filters follow the voice you select, and
changing a filter clears a voice that no longer matches it. Voices that Telnyx
reports without a language stay visible under every language filter.

The speaker button next to the field plays a sample of the selected voice at
the configured speed, spoken by Telnyx itself. Use it before saving: the same
endpoint validates the voice and speed combination that the assistant uses for
its greeting, so an unusable pair is reported in the form instead of ending
every call after one second. The sample reads the assistant greeting, or a
standard sentence when that greeting contains dynamic variables. Only Connect
administrators can play it, since each sample spends Telnyx text-to-speech
credit.

The catalog behind the selector is the cached account catalog shared with
**System Voice**. Refresh it with **REFRESH VOICES** in the Telnyx settings
after adding or cloning a voice in the Telnyx portal.

**Voice Speed** must be between 0.5 and 1.5, and 1.0 is the safe default.
Telnyx documents a wider range for its Natural voices only; another voice
rejects a speed it does not support, and that failure is invisible until a
call arrives — the assistant answers, cannot synthesize its greeting and hangs
up after about one second. Telnyx Ultra, for example, needs at least 0.8. If
calls end immediately after being answered, check the assistant conversation
in the Telnyx portal for "could not generate the greeting audio" and return
the speed to 1.0.

**Voice Language Boost** is an optional TTS hint chosen from the languages
Telnyx supports. Use **Automatic** with a supported multilingual voice, select
an explicit language when one assistant is intentionally fixed to it, or leave
it empty to keep the provider default. **Expressive Mode** lets Telnyx Ultra
voices add contextual expression; the switch appears only while such a voice
is selected and clears itself when you move to another provider. Both values
are stored in Odoo and published by automatic sync and **Push to Telnyx**.

- **Enable Contact Tools** allows strict contact lookup and adding internal
  notes.
- **Register Call Request** is always available to save the qualified reason,
  context, and agreed next step as an internal note on the current call.
- **Enable CRM Tools** allows creation/update of an open CRM lead when CRM is
  installed.
- **Enable Helpdesk Tools** allows creation/update of a ticket when Helpdesk is
  installed.
- **Memory Enabled** asks Telnyx to retrieve recent conversations for the same
  caller. It is Telnyx conversation memory and is independent of the Odoo
  `connect_memory` module.

Recording and memory are off by default. CRM and Helpdesk tools are published
only when the matching Odoo models are installed.

The **Turn Taking** group controls when the assistant decides the caller has
finished and starts answering. **Wait Before Speaking** (default 0.4 s) is the
silence it sits through before replying. The three endpointing values are the
silence that ends the caller's turn: **Pause Without Punctuation** (default
1.0 s) applies while the transcript has no sentence end and is the one that
keeps the agent out of a pause taken mid-thought, **Pause After Punctuation**
(0.3 s) applies to a finished sentence, and **Pause After Numbers** (0.6 s)
applies while digits are being dictated. Raise the values if the agent talks
over callers, lower them if it feels sluggish. **Caller Can Interrupt** lets
the caller cut the agent off; **Protect Greeting** ignores speech until the
greeting has played.

These settings matter because the configured transcription model decides
nothing about turn taking: with `deepgram/nova-3` the endpointing plan is the
only thing separating a pause from the end of a sentence. Telnyx ships a
0.1-second plan, which is what makes an agent finish your sentences for you.

**Caller Silence Timeout** stops the assistant after that much silence from
the caller, and defaults to 60 seconds. Telnyx accepts 10 to 14,400 seconds.
Keep it set: Telnyx never ends a conversation on its own, it only keeps
notifying the assistant about the silence, so a caller who walks away or loses
audio leaves the call running until **Call Time Limit** expires — one abandoned
call was observed answering 45 silence events over 17 minutes. Setting the
field to 0 restores that unlimited behavior. Existing assistants receive the
60-second default on module upgrade and publish it at the next sync or **Push
to Telnyx**.

When assistant recording is enabled, Telnyx produces the audio, conversation
messages, and configured insight summary. Odoo stores all three on one
**Recordings** row after the call. The audio is downloaded into an Odoo
attachment because Telnyx's signed download URL expires. Telnyx is already the
transcription provider for this path, so the recording is never sent to
OpenAI for a second transcription, even when global call transcription is
enabled.

The summary wording is configured in **Telnyx -> Configuration -> Settings**,
field **AI Summary Instructions**. It is the prompt of the Telnyx conversation
insight Odoo owns. Saving a new text deletes the current insight in Telnyx and
recreates it with the new wording inside the same insight group, so the webhook
address does not change and summaries generated earlier keep their original
wording. When no insight exists yet, the text is simply used by the next
account sync.

The signed insight webhook normally performs this synchronization immediately.
**Sync Telnyx AI Conversations** runs every five minutes as an idempotent repair
for delayed or missed callbacks. Sanitized development databases commonly have
scheduled actions disabled; run that action manually when testing historical
calls in such an environment.

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
names with gender and the underlying Telnyx ID. The speaker button next to the
field plays a sample of the selected voice. Click **REFRESH VOICES** after
adding a voice in Voice Design Lab. The normal **SYNC TELNYX ACCOUNT** action
refreshes the same catalog. If the catalog cannot be fetched, the current
selection and the basic TeXML voices remain available.

AI assistants use the same catalog without the basic TeXML voices (`man`,
`woman`, `alice`), which only exist for `<Say>` and cannot drive an assistant.

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

If an optional WhatsApp/RCS resource or an Odoo AI Assistant cannot be
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
- Outbound PSTN calls from SIP hardphones go directly through the credential
  connection. Internal assistant extensions use the configured Odoo SIP
  subdomain and TeXML router.
