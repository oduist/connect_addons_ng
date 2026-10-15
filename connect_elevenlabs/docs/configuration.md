# Account Configuration

Open **Connect ▸ ElevenLabs ▸ Configuration ▸ Settings** (Connect Administrator
only). This standalone form edits the shared `connect.settings` singleton but
exposes **only** the ElevenLabs fields (opened via `open_elevenlabs_form()`).

!!! note "Set the public API URL first"
    ElevenLabs settings live on the shared `connect.settings` record, which also
    holds the core **API URL**. Set it (in **Connect ▸ Configuration ▸
    Settings**) to your public HTTPS Odoo URL, e.g. `https://odoo.example.com`,
    before syncing. Both webhook URLs the module registers with ElevenLabs (the
    conversation-initiation webhook and the post-call webhook) are built from
    this value, as are the URLs of every server tool.

## API tab

| Field | Description |
|-------|-------------|
| **Enabled** (`elevenlabs_enabled`) | Master switch for the integration. When off, ElevenLabs TTS prompts, transcription and webhook pushes are all skipped and the base Twilio behaviour is used. |
| **API Key** (`display_elevenlabs_api_key`) | Your ElevenLabs API key. Stored on the protected `elevenlabs_api_key` field (restricted to `base.group_erp_manager`), shown masked (`****`) to everyone else, and never exposed to the webhook identity. Leading/trailing whitespace is stripped when the client is built. |
| **Selected Voice** (`elevenlabs_voice`) | The default voice used for text-to-speech file generation (call-flow prompts, voicemail greetings). Populated from the synced voice library. |

Generate the API key in the ElevenLabs dashboard under **Developers → API
Keys** (direct link: [elevenlabs.io/app/settings/api-keys](https://elevenlabs.io/app/settings/api-keys)).
The full key is shown only once, at creation. The form also links to **OPEN A
NEW ELEVENLABS ACCOUNT HERE** (shown until a key is set) and to the ElevenLabs
shared voice library.

### Action buttons

| Button | Method | What it does |
|--------|--------|--------------|
| **SYNC** | `elevenlabs_sync` | Full sync: imports voices, **regenerates the agent token** and re-pushes both webhooks, syncs all non-system tools, then updates every agent in ElevenLabs. Skipped if the license check fails. |
| **UNBIND ACCOUNT** | `elevenlabs_unbind_account` | Clears all local `agent_uid` and tool `tool_id` values so records can be re-synced to a **different** ElevenLabs account. Does not touch the remote account. |
| **REGENERATE PROMPTS** | `elevenlabs_regenerate_prompts` | Re-generates the ElevenLabs TTS audio files for every Twilio call-flow prompt, invalid-input and voicemail message. |
| **SYNC TOOLS** | `elevenlabs_sync_tools` | Creates or updates every non-system tool in ElevenLabs (system tools are managed inside agent config, not as standalone tools). |

!!! info "How a sync flows"
    `SYNC` calls, in order: `elevenlabs_get_voices()` → `elevenlabs_reset_token()`
    (new token + re-push initiation and post-call webhooks) → `elevenlabs_sync_tools()`
    → `update_elevenlabs_agent()` for every agent. Run it after changing the API
    key, after binding a new account, or whenever tools/agents drift from the
    remote workspace.

## Webhook tab

Visible once the integration is enabled and an API key is set. It shows the
computed **Conversation Initiation Webhook URL**
(`…/connect_elevenlabs/conversation_initiation`).

Both the conversation-initiation webhook and the post-call webhook are pushed to
your **ElevenLabs workspace settings** automatically on **SYNC** — the module
does not use per-agent webhook overrides. Along with the initiation URL, a shared
secret token is registered; ElevenLabs echoes it back as the
`x-elevenlabs-agent-token` header on every webhook and server-tool call
(conversation initiation, transfer, create-partner, the calendar tools). To
rotate the token, run **SYNC** again — it regenerates the token and re-pushes it
to the workspace settings and to every server tool.

See [Webhooks & Security](webhooks-security.md) for the full route list and how
each webhook is authenticated.

## Voices

Voices are stored in `connect.elevenlabs_voice` and refreshed from the ElevenLabs
voice library (`voices.get_all()`) on every **SYNC** (or via **Voices** menu).
Each voice keeps its `voice_id`, name, language, accent, age, gender and a
preview-audio player. Voices removed from your ElevenLabs account are removed
locally, and if the **Selected Voice** setting is empty it is auto-assigned. Add
more voices to your account from the ElevenLabs shared voice library, then SYNC.

## Transcript provider

Enabling the integration also adds **ElevenLabs** as an option on the core
**Transcript Provider** setting. When set to `elevenlabs`, recording
transcription uses ElevenLabs Speech-to-Text (`scribe_v1`) with an OpenAI-written
summary; otherwise the core provider is used. See
[Maintenance ▸ Transcription](maintenance.md#recordings-transcription).
