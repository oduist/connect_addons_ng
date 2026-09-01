# Core Configuration

Core settings are managed in **Connect > Configuration > Settings**.
Provider-specific settings have their own menus: **Connect > Twilio > Configuration >
Settings**, **Connect > FreeSWITCH > Configuration > Settings**, **Connect > Asterisk >
Configuration > Settings**.

## General Tab

| Setting | Description |
|---------|-------------|
| **Debug Mode** | Enable detailed debug logging. Logs are auto-cleaned daily. |
| **Number Search Operation** | How partner phone numbers are matched: `=` (exact) or `like` (pattern). Exact is faster; pattern handles formatting differences. |
| **Proxy Recordings** | When enabled, recording audio is served through Odoo (requires authentication). When disabled, direct URLs to the provider's storage are used. |

## Transcription Tab

Connect uses OpenAI for automatic call transcription and summarization.

| Setting | Description |
|---------|-------------|
| **Enable Call Transcription** | Automatically transcribe recordings when they are created. |
| **Delete Recording After Transcription** | Delete the Odoo recording and its attachment after transcript and summary are stored on the linked call. Disabled by default. |
| **Transcription Provider** | Currently supports OpenAI. |
| **OpenAI API Key** | Your OpenAI API key. Masked in the UI for non-managers. |
| **Summary Model** | OpenAI model used for call summaries. Defaults to GPT-5.4 mini; GPT-4o remains available. |
| **Register Summary** | Automatically post call summaries to the partner's chatter. |
| **Summary Prompt** | Custom prompt for call summarization. Default: "Summarise this phone call". |

!!! info "How transcription works"
    1. A call recording is created and added to the transcription queue
    2. The **Connect: transcribe pending recordings** scheduled action runs every two minutes
    3. Audio is sent to OpenAI Whisper API for speech-to-text
    4. The estimated Whisper cost is stored from OpenAI's processed duration
    5. The transcript is sent to the selected summary model with the summary prompt
    6. The transcript and summary are saved permanently on the call record
    7. If **Delete Recording After Transcription** is enabled, the successfully processed Odoo recording is deleted
    8. If enabled, the summary is posted to the partner's chatter

    The scheduled action must be active for automatic processing. Sanitized
    development or staging databases may have scheduled actions disabled. A
    manual transcription removes the recording from the queue, and the cron
    skips already-transcribed recordings to avoid duplicate OpenAI requests.

    Automatic deletion only applies to recordings linked to a call and only
    after successful transcription and summarization. Failed or unlinked
    recordings are kept. This setting removes the Odoo row and any Odoo-managed
    attachment; configure provider-side audio retention separately.


## PBX Users

Navigate to **Connect > Users** to create PBX user accounts.

| Field | Description |
|-------|-------------|
| **Odoo User** | Link to an Odoo user account. One PBX user per Odoo user. |
| **Record Calls** | Enable call recording for this user. Default: enabled. |
| **Voicemail Enabled** | Allow callers to leave voicemail when user is unavailable. |
| **Voicemail Prompt** | Custom voicemail greeting (supports Jinja2 templates). |
| **Greeting Message** | Message spoken to the caller before ringing the user. |
| **Language** | TTS language used to speak the greeting and voicemail prompt. Default: English (US). |
| **Voice** | Provider-specific TTS voice name (e.g. `Woman` for Twilio, `Polly.Joanna` for Twilio/Telnyx). Leave empty to use the provider default. |
| **Missed Call Notifications** | Send notifications for missed calls. |
| **Click-to-call Provider** | Which installed telephony module originates calls for this user. Leave empty when only one provider module is installed. |
| **Messaging Provider** | Which installed messaging module sends SMS/WhatsApp for this user. Leave empty when only one messaging module is installed. |
| **Summary Prompt** | Per-user prompt for AI call summaries, taking the place of the system-wide **Summary Prompt** from the Transcription settings. |

Provider-specific fields (Twilio username/SIP domain, per-provider extension
numbers, outgoing caller IDs, endpoints) are added to the user form by the
installed integration modules. When a PBX user is created, the Twilio and
FreeSWITCH integrations automatically assign an extension number in their own
numbering plans.

## Phone Numbers (DIDs)

Inbound phone numbers belong to the telephony provider: navigate to
**Connect > Twilio > Numbers**, **Connect > FreeSWITCH > Numbers** or **Connect > Asterisk > Numbers**.

| Field | Description |
|-------|-------------|
| **Phone Number** | The DID number (e.g., +1234567890). |
| **Friendly Name** | Human-readable label. |
| **Destination** | Route incoming calls to a **User** or **Call Flow** (Twilio/FreeSWITCH; Asterisk numbers only map a DID to a user for dialplan lookups). |
| **Default** | Mark as the default outgoing number. |

## Outgoing Caller IDs

Outgoing caller IDs also belong to the provider: navigate to
**Connect > Twilio > Outgoing Caller IDs** or **Connect > FreeSWITCH > Outgoing Caller IDs**.

Numbers must start with `+` followed by digits only. Only one caller ID can be marked as default at a time.

The caller ID flagged **Default** is presented on outbound calls for users
who have no per-user **Outgoing Caller ID** assigned. This system-wide
fallback applies to both the Twilio and FreeSWITCH integrations; with no
default set, FreeSWITCH falls back to the user's extension number.

## Extensions

Extensions are auto-managed per provider. When you create a PBX user or call
flow, an extension number is automatically assigned in that provider's
numbering plan. View extensions in **Connect > Twilio > Extensions** or
**Connect > FreeSWITCH > Extensions**. (The Asterisk integration keeps numbering in your
existing dialplan — the user form only mirrors the extension as plain text.)

## Message Configuration

Navigate to **Connect > Twilio > Messages > Message Configuration** to configure automatic partner creation from incoming messages.

| Field | Description |
|-------|-------------|
| **Number** | Which inbound number triggers auto-creation. |
| **Destination** | Target model (res.partner). |
| **Default Values** | Python dict of default field values for created records. |
