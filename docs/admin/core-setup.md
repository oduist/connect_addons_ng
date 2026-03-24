# Core Configuration

All settings are managed in **Connect > Configuration > Settings**.

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
| **Transcription Provider** | Currently supports OpenAI. |
| **OpenAI API Key** | Your OpenAI API key. Masked in the UI for non-managers. |
| **Register Summary** | Automatically post call summaries to the partner's chatter. |
| **Summary Prompt** | Custom prompt for GPT-4o summarization. Default: "Summarise this phone call". |

!!! info "How transcription works"
    1. A call recording is created (by Twilio or FreeSWITCH)
    2. Audio is sent to OpenAI Whisper API for speech-to-text
    3. The transcript is sent to GPT-4o with the summary prompt
    4. The summary is saved on both the recording and the call record
    5. If enabled, the summary is posted to the partner's chatter


## PBX Users

Navigate to **Connect > PBX > Users** to create PBX user accounts.

| Field | Description |
|-------|-------------|
| **Username** | Alphanumeric PBX identifier (required, unique). |
| **Odoo User** | Link to an Odoo user account. One PBX user per Odoo user. |
| **Record Calls** | Enable call recording for this user. Default: enabled. |
| **Voicemail Enabled** | Allow callers to leave voicemail when user is unavailable. |
| **Voicemail Prompt** | Custom voicemail greeting (supports Jinja2 templates). |
| **Outgoing Caller ID** | Default outgoing number for this user. |
| **Missed Call Notifications** | Send notifications for missed calls. |

When a PBX user is created, an extension number is automatically assigned.

## Phone Numbers (DIDs)

Navigate to **Connect > PBX > Numbers** to manage inbound phone numbers.

| Field | Description |
|-------|-------------|
| **Phone Number** | The DID number (e.g., +1234567890). |
| **Friendly Name** | Human-readable label. |
| **Destination** | Route incoming calls to a **User** or **Call Flow**. |
| **Default** | Mark as the default outgoing number. |

## Outgoing Caller IDs

Navigate to **Connect > PBX > Caller IDs** to manage outgoing numbers.

Numbers must start with `+` followed by digits only. Only one caller ID can be marked as default at a time.

## Extensions

Extensions are auto-managed. When you create a PBX user or call flow, an extension number is automatically assigned. View all extensions in **Connect > PBX > Extensions**.

## Message Configuration

Navigate to **Connect > Configuration > Message Config** to configure automatic partner creation from incoming messages.

| Field | Description |
|-------|-------------|
| **Number** | Which inbound number triggers auto-creation. |
| **Destination** | Target model (res.partner). |
| **Default Values** | Python dict of default field values for created records. |
