# Connect Pipecat Module Specification

## Module info

- **Name:** Oduist Connect Pipecat
- **Technical:** `connect_pipecat`
- **Version:** 19.0.1.0.0
- **Depends:** `connect`, `connect_freeswitch`
- **Application:** False
- **License:** Other proprietary

## Purpose and architecture

`connect_pipecat` adds configurable inbound AI voice agents to the
FreeSWITCH integration. Pipecat runs in the `oduist/pipecat-agent` sidecar;
Odoo remains the configuration and call-record system. The sidecar supports
OpenAI and Deepgram STT, OpenAI and Anthropic LLMs, and OpenAI, ElevenLabs and
Deepgram TTS.

The call path is:

1. A `connect.exten` resolves to `connect.pipecat.agent`.
2. Odoo renders a dialplan that answers, waits 500 ms, configures WebSocket
   Basic auth, starts `uuid_audio_fork` in bidirectional raw-stream mode and
   parks the channel.
3. The sidecar authenticates FreeSWITCH, loads agent configuration from Odoo,
   and runs a 16 kHz Pipecat pipeline with Silero VAD.
4. Pipecat interruption frames send `killAudio`; generated audio is returned as
   binary L16. Tool calls ask Odoo to transfer or hang up through XML-RPC.
5. At completion, the sidecar posts transcript and summary to Odoo.

See ADR-030 for the transport decision and security boundaries.

## Models

### `connect.pipecat.agent`

| Field | Type | Notes |
|---|---|---|
| `name`, `active` | Char, Boolean | Display name and archive toggle |
| `system_prompt`, `greeting` | Text | Required system behavior and optional first spoken line |
| `language` | Selection | Shared Connect BCP-47 language list |
| `stt_provider`, `stt_model` | Selection, Char | OpenAI or Deepgram |
| `llm_provider`, `llm_model` | Selection, Char | OpenAI or Anthropic |
| `tts_provider`, `tts_model`, `tts_voice` | Selection, Char, Char | OpenAI, ElevenLabs or Deepgram |
| `transfer_exten`, `transfer_prompt` | Many2one, Text | Optional human destination and tool guidance |
| `max_duration` | Integer | Positive call/session timeout in seconds |
| `record_calls` | Boolean | Enables the existing FreeSWITCH recording webhook |
| `exten`, `exten_number` | Many2one, related Char | Back-reference to the agent extension |

`create_extension()` opens the standard extension form.
`generate_dialplan(params, exten=None)` renders
`dialplan_pipecat_agent` through `connect.freeswitch.template`.

### `connect.exten`

Adds `('connect.pipecat.agent', 'AI Agent')` to the `dst` reference.

### `connect.settings`

Adds the sidecar base URL, shared service token, provider keys and a status
probe. Stored secrets are admin-only. Display twins participate in the core
`PROTECTED_FIELDS` masking flow. `get_pipecat_ws_url()` and
`get_pipecat_http_url()` translate the configured scheme for media and health
requests respectively.

## HTTP API

All routes require `Authorization: Bearer <pipecat_service_token>` and fail
closed when no token is configured. Mutating Odoo 19 routes set
`readonly=False`.

| Method and route | Purpose |
|---|---|
| `GET /pipecat/agent/<id>` | Active agent config and only the selected providers' credentials |
| `POST /pipecat/call-result` | Set `connect.call.summary` and update an existing `connect.recording` transcript/summary |
| `POST /pipecat/hangup` | Execute `uuid_kill <call_uuid>` |
| `POST /pipecat/transfer` | Stop `uuid_audio_fork`, then execute `uuid_transfer` to `transfer_exten` |

Requests execute with `connect.user_connect_webhook` model access after token
validation. Settings and provider keys are read with `sudo()` because the
settings model is admin-only.

## Sidecar

The Python 3.12 service is under `connect_pipecat/deploy`. It pins Pipecat
1.5.0 and exposes authenticated `GET /health` and Basic-authenticated `WS /ws`.
Each WebSocket owns one pipeline and one Odoo client. Provider factories use
Pipecat's canonical runtime `Settings` API. Deepgram smart formatting is
disabled to avoid splitting conversational utterances into premature finals.

`AudioForkFrameSerializer` maps raw binary PCM to `InputAudioRawFrame`, output
audio to 16 kHz binary PCM, interruptions to `killAudio`, and terminal frames
to `disconnect`. Transfer state suppresses the terminal hangup callback so a
successful `uuid_transfer` is not immediately killed.

## Security

`connect.group_user` has read-only agent access, per the product decision.
`connect.group_admin` has CRUD. `connect.group_webhook` has read-only access
plus an all-record read rule. No non-admin group has access to settings or
stored provider secrets.

## Deferred

DTMF, outbound campaigns, Twilio media transport and FlowManager IVR are not
part of version 1.
