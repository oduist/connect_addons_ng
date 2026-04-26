# ElevenLabs Integration Setup

## Prerequisites

- An ElevenLabs account with conversational-AI access ([elevenlabs.io](https://elevenlabs.io))
- An ElevenLabs API key (Profile → API Keys)
- A public URL for the media-bridge service (see "Media Bridge" below)
- Twilio integration already configured (`connect_twilio`) — ElevenLabs rides over Twilio Media Streams

## Account Configuration

Navigate to **Connect → Configuration → Settings** and open the **ElevenLabs** tab.

### Credentials

| Field | Description |
|---|---|
| **ElevenLabs API Key** | API key with ConvAI access. Masked for non-managers. |
| **Agent Token** | Shared secret sent in the `x-elevenlabs-agent-token` header by ElevenLabs when calling back the agent tool webhooks. Rotated by the **Reset Token** action. |
| **Post Call Webhook Secret** | HMAC secret for `elevenlabs-signature` header validation on post-call webhooks. Masked for non-managers. |
| **Agent URL** | Public URL of the FastAPI media-bridge service (see below). |
| **Default Voice** | ElevenLabs voice used for TTS playback of callflow/voicemail prompts. |
| **Enabled** | Master switch. When off, the module falls back to standard Twilio `<Say>` TTS. |

### Actions

- **Sync Voices** — pull the ElevenLabs voice catalogue into Odoo.
- **Sync Tools** — push every non-system `connect.elevenlabs_agent_tool` to ElevenLabs.
- **Sync Agents** — push every `connect.elevenlabs_agent` to ElevenLabs.
- **Full Sync** — voices + tools + agents + rotate agent token.
- **Regenerate Prompts** — regenerate every cached TTS audio file for callflow prompts and voicemail greetings.
- **Unbind Account** — clear all local `agent_uid` / `tool_id` values so the next sync re-creates everything in a fresh ElevenLabs account.
- **Ping Agent** — verify the media-bridge service can reach Odoo via JSON-RPC.

## Webhook URLs

Configure these on the ElevenLabs side (Agent → Analysis → Post-call webhook):

| Endpoint | Purpose |
|---|---|
| `<api_url>/connect_elevenlabs/post_call` | Receives conversation summary, transcript, and audio URL after every call. Validates the `elevenlabs-signature` header. |
| `<api_url>/connect_elevenlabs/transfer` | Called by the `transfer_to_exten` agent tool. Validates `x-elevenlabs-agent-token`. |
| `<api_url>/connect_elevenlabs/get_available_slots` | Calendar lookup tool. |
| `<api_url>/connect_elevenlabs/create_event` | Calendar event creation tool. |
| `<api_url>/connect_elevenlabs/get_meetings` | Partner meeting list tool. |
| `<api_url>/connect_elevenlabs/remove_meeting` | Calendar event removal tool. |
| `<api_url>/connect_elevenlabs/get_current_date` | Utility tool. |

Copy the **Post Call Webhook URL** shown in the settings into the ElevenLabs dashboard.

## Media Bridge

Call audio flows from Twilio Media Streams through a small FastAPI service that proxies bidirectional audio to the ElevenLabs Conversational AI WebSocket.

```
Twilio call  →  <Connect><Stream url="wss://bridge/twilio/stream/..."/>  →  FastAPI bridge  →  ElevenLabs ConvAI
```

The bridge source lives in `connect_elevenlabs/service/` (Dockerfile + `main.py`).

### Environment variables

| Variable | Description |
|---|---|
| `ELEVENLABS_API_KEY` | Same key entered in Odoo settings. |
| `ODOO_URL` | Base URL of the Odoo instance (e.g. `https://connect.example.com`). |
| `ODOO_DB` | Odoo database name. |
| `ODOO_USER` | Login of a user with `connect.group_webhook`. |
| `ODOO_PASSWORD` | That user's password. |

Run on port 48000 behind HTTPS; the `Agent URL` field in Odoo must point at the public HTTPS URL.

### Deployment

```bash
docker build -t connect-elevenlabs-bridge connect_elevenlabs/service/
docker run -d --env-file bridge.env -p 48000:48000 connect-elevenlabs-bridge
```

Verify with the **Ping Agent** button in Odoo.

## Transcription Provider

The **Transcript Provider** setting (on the Transcription tab) now includes an **Elevenlabs** option. When selected, recording transcription uses `scribe_v1` STT with diarization instead of OpenAI Whisper. The summary step still uses OpenAI GPT-4o; configure `openai_api_key` on the Transcription tab as usual.

## Licensing

`connect_elevenlabs` requires a valid Oduist license. Check **Oduist → Licenses** to confirm entitlement; extensions (`_helpdesk`, `_knowledge`, `_sale`) are licensed separately.
