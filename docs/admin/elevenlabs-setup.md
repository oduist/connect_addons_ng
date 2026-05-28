# ElevenLabs Integration Setup

## Prerequisites

- An ElevenLabs account with conversational-AI access ([elevenlabs.io](https://elevenlabs.io))
- An ElevenLabs API key (Profile → API Keys)
- A public HTTPS URL for your Odoo instance (required for ElevenLabs to reach the conversation initiation webhook)

## Account Configuration

Navigate to **Connect → Configuration → Settings** and open the **ElevenLabs** tab.

### Credentials

| Field | Description |
|---|---|
| **ElevenLabs API Key** | API key with ConvAI access. Masked for non-managers. |
| **Agent Token** | Shared secret sent in the `x-elevenlabs-agent-token` header by ElevenLabs when calling back the agent tool webhooks. Rotated by the **Reset Token** action. |
| **Post Call Webhook Secret** | HMAC secret for `elevenlabs-signature` header validation on post-call webhooks and conversation initiation webhooks. Masked for non-managers. |
| **Default Voice** | ElevenLabs voice used for TTS playback of callflow/voicemail prompts. |
| **Enabled** | Master switch. When off, the module falls back to standard Twilio `<Say>` TTS. |

### Actions

- **Sync Voices** — pull the ElevenLabs voice catalogue into Odoo.
- **Sync Tools** — push every non-system `connect.elevenlabs_agent_tool` to ElevenLabs.
- **Sync Agents** — push every `connect.elevenlabs_agent` to ElevenLabs.
- **Full Sync** — voices + tools + agents + rotate agent token.
- **Regenerate Prompts** — regenerate every cached TTS audio file for callflow prompts and voicemail greetings.
- **Unbind Account** — clear all local `agent_uid` / `tool_id` values so the next sync re-creates everything in a fresh ElevenLabs account.

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

## Conversation Initiation Webhook

When an agent record is saved, `update_elevenlabs_agent()` automatically writes the conversation initiation webhook URL into the agent's platform settings on ElevenLabs. The URL is:

```
<base_url>/connect_elevenlabs/conversation_init
```

ElevenLabs calls this endpoint before connecting each inbound SIP call so Odoo can inject dynamic variables (caller context, previous conversation history, available extensions) into the agent session.

### Authentication

The `conversation_init` route is HMAC-authenticated using the same secret stored in **Post Call Webhook Secret** (`elevenlabs_post_call_webhook_secret`). ElevenLabs signs both the conversation initiation request and post-call webhook with the workspace's webhook secret.

> **Deployment note:** Operators must configure the **same** secret in both Odoo (the `elevenlabs_post_call_webhook_secret` field) and the ElevenLabs workspace webhook settings. A mismatch causes a `401 Unauthorized` response on every inbound call attempt.

## Transcription Provider

The **Transcript Provider** setting (on the Transcription tab) now includes an **Elevenlabs** option. When selected, recording transcription uses `scribe_v1` STT with diarization instead of OpenAI Whisper. The summary step still uses OpenAI GPT-4o; configure `openai_api_key` on the Transcription tab as usual.

## Licensing

`connect_elevenlabs` requires a valid Oduist license. Check **Oduist → Licenses** to confirm entitlement; extensions (`_helpdesk`, `_knowledge`, `_sale`) are licensed separately.

## Choosing a provider for an agent

Each ElevenLabs agent must be bound to one telephony provider — the
one that routes calls to it. Pick the provider in the agent form
header. Twilio agents accept inbound SIP from Twilio's signaling
range by default; FreeSWITCH agents allow all by default — restrict
this in production via the *SIP Routing* tab.

The provider is locked once you assign an extension to the agent.
To switch provider on an existing agent, first remove the extension,
change the provider, then re-assign an extension.
