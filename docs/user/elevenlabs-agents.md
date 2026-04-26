# ElevenLabs Conversational AI Agents

`connect_elevenlabs` lets an ElevenLabs conversational AI answer and handle phone calls on your behalf. This page covers day-to-day use — agent creation, voices, tools, templates, and how calls flow.

## Creating an Agent

1. Open **Connect → ElevenLabs → Agents** and click **New**.
2. Pick a **Template** (optional) to pre-fill the system prompt.
3. Fill in the required fields:
    - **Name** — internal label.
    - **Voice** — one of the synced ElevenLabs voices.
    - **First Message** — the greeting the caller hears.
    - **Prompt** — the agent's system prompt.
    - **Language** — primary conversation language.
    - **Additional Languages** — preload extra languages; translations of **First Message** are pushed as language presets.
    - **Tools** — pick which agent tools the AI may call (see below).
4. Save. Odoo creates the agent on ElevenLabs and stores the returned `agent_uid`.

Every edit to **Prompt** creates a new version under **Prompt Versions**, so you can roll back.

## Voices

Voices are a read-only catalogue synced from ElevenLabs. Refresh the list from the **ElevenLabs** settings tab (**Sync Voices**). Click a row to preview the audio.

## Tools

Tools let the agent do things mid-call. Three kinds are supported:

| Kind | When to use |
|---|---|
| **System** | ElevenLabs built-ins: `end_call`, `skip_turn`, `language_detection`, `play_keypad_touch_tone`, `voicemail_detection`, `transfer_to_agent`. Configured through agent settings, not as separate HTTP webhooks. |
| **Webhook** | Your own HTTP endpoint. For each parameter pick a **value type**: `LLM Prompt` (the agent decides), `Dynamic Variable` (injected from call context), or `Constant Value`. |
| **Client** | Runs in the client-side media bridge. Used for instant actions like `transfer_to_extension`. |

Out of the box you get:

- `transfer_to_exten` — human handoff; the agent extracts the target extension from `{{available_extensions}}`.
- Calendar tools: `calendar_get_available_slots`, `calendar_create_event`, `calendar_get_current_date`, `calendar_get_meetings`, `calendar_remove_meeting`.

Tickets, sale orders, and knowledge search tools are delivered by the companion modules (`connect_elevenlabs_helpdesk`, `connect_elevenlabs_sale`, `connect_elevenlabs_knowledge`).

## Agent Templates

**Connect → ElevenLabs → Agent Templates** holds reusable system prompts. Selecting a template on a new agent form copies its prompt into the agent's `prompt` field — you can then edit freely.

## Knowledge Base (requires `connect_elevenlabs_knowledge`)

Attach URLs, files (`.epub .pdf .docx .txt .html .md`), or inline text to an agent via the **Knowledge** tab on the agent form. Documents are pushed to ElevenLabs and referenced in the agent's prompt config once `state` is `active`.

## How a Call Flows

1. Caller dials a Twilio DID whose **Destination** is **Agent**.
2. Twilio fetches TwiML from `connect_elevenlabs` which emits `<Connect><Stream>` at the media bridge.
3. The media bridge opens a WebSocket to ElevenLabs Conversational AI, dynamic-variables loaded from Odoo: partner, previous summary, available extensions, caller TZ/language.
4. Agent talks to the caller. Tool calls hit Odoo via the `/connect_elevenlabs/*` endpoints.
5. At hangup ElevenLabs POSTs to `/connect_elevenlabs/post_call`. Odoo stores summary + transcript + mp3 on the call's recording.

## Transfer

The agent can transfer the caller to any **Published Extension** using the `transfer_to_exten` tool. If a single published extension is configured, the agent falls back to it even when the caller names a non-existent number.

## Recordings & Transcripts

Agent calls produce a standard `connect.recording` with an `elevenlabs_transcript`, `elevenlabs_summary`, and the conversation audio. The call form shows an audio widget and a full transcript.

## Troubleshooting

- **Agent does not pick up** — verify the DID destination is set to Agent, the agent has an `agent_uid`, and the media bridge is reachable. Click **Ping Agent** on settings.
- **Missing transcript or summary** — confirm the post-call webhook secret matches the ElevenLabs dashboard and that the webhook URL is publicly reachable.
- **Tool returns "Unauthorized"** — the `x-elevenlabs-agent-token` header differs from the Odoo-side token. Click **Reset Token** then **Sync Tools** to propagate.
- **Voicemail/IVR audio sounds robotic** — **Enabled** is off; turn it on and click **Regenerate Prompts** to refresh cached mp3 files.
