# Connect ElevenLabs Module Specification

## Module Info

- **Name:** Oduist Connect ElevenLabs
- **Technical:** `connect_elevenlabs`
- **Version:** 19.0.1.0.0
- **Depends:** `connect`, `connect_twilio`, `calendar`
- **Python deps:** `elevenlabs`
- **Application:** False
- **License:** Other proprietary

## Overview

`connect_elevenlabs` adds ElevenLabs conversational-AI agent support on top of `connect` + `connect_twilio`. It stores agents, voices, tools, knowledge references, and TTS audio files in Odoo, synchronises agents and tools with the ElevenLabs REST API, and handles post-call / transfer / calendar webhooks.

For call routing the module emits TwiML `<Connect><Stream url=…>` that hands audio to a companion FastAPI media bridge (`service/`) which terminates Twilio Media Streams and proxies audio to the ElevenLabs conversational-AI WebSocket. That is why the module depends on `connect_twilio` today — see ADR-014 for why an agnostic core module is not split out yet.

---

## Models (connect_elevenlabs/models/)

### 1. settings.py — `_inherit = 'connect.settings'`

Adds ElevenLabs API credentials, webhook token, and transcript-provider selection.

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `elevenlabs_api_key` | Char | groups `base.group_erp_manager` |
| `display_elevenlabs_api_key` | Char | masked via `PROTECTED_FIELDS` |
| `elevenlabs_agent_token` | Char | UUID default; groups `base.group_erp_manager` |
| `elevenlabs_voice` | Many2one (`connect.elevenlabs_voice`) | Default TTS voice |
| `elevenlabs_enabled` | Boolean | Master switch used by callflow/user TTS |
| `elevenlabs_agent_url` | Char | Public URL of the FastAPI media bridge |
| `elevenlabs_agent_parameters` | Text | |
| `elevenlabs_post_call_webhook_url` | Char (compute) | `<api_url>/connect_elevenlabs/post_call` |
| `elevenlabs_post_call_webhook_secret` | Char | groups `base.group_erp_manager` |
| `display_elevenlabs_post_call_webhook_secret` | Char | masked |
| `transcript_provider` | Selection | `selection_add=[('elevenlabs', 'Elevenlabs')]` |

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `get_elevenlabs_client()` | Instantiate `elevenlabs.ElevenLabs(api_key=…)` |
| `elevenlabs_get_voices()` | Pull voice catalogue from ElevenLabs |
| `elevenlabs_regenerate_prompts()` | Regenerate all TTS prompt files for callflows |
| `elevenlabs_sync_ai_agents()` | Push local agents to ElevenLabs |
| `elevenlabs_sync_tools()` | Push non-system tools to ElevenLabs |
| `elevenlabs_reset_token()` | Rotate `elevenlabs_agent_token` |
| `elevenlabs_sync()` | Full sync: voices + token + tools + agents |
| `elevenlabs_unbind_account()` | Clear all `agent_uid` / `tool_id` values |
| `ping_agent()` | Ping the media-bridge FastAPI endpoint |
| `open_elevenlabs_form()` | Action: open the ElevenLabs settings tab |

Registers itself in `ODUIST_MODULES` and appends its two protected display fields to `PROTECTED_FIELDS`.

---

### 2. agent.py — `connect.elevenlabs_agent` (NEW)

The main agent record. Stores prompt, voice, language settings, LLM choice, limits; syncs to ElevenLabs on create/write/unlink.

**Fields (abbreviated):** `name`, `voice` (Many2one `connect.elevenlabs_voice`, required), `first_message`, `prompt`, `prompt_version_ids` (One2many), `active_prompt_version`, `language` (Selection of 33 ISO codes), `additional_languages` (Many2many `res.lang`), `tools` (Many2many `connect.elevenlabs_agent_tool`), `temperature`, `max_tokens`, `llm` (Selection spanning OpenAI, Gemini, Anthropic, ElevenLabs-hosted, Grok), `agent_uid` (ElevenLabs ID), `use_flash`, `output_audio_format` / `user_input_audio_format` (Selection), `model` (ElevenLabs TTS model), `stability`, `speed`, `max_duration_seconds`, `agent_concurrency_limit`, `daily_limit`, `similarity_boost`, `turn_timeout`, `silence_end_call_timeout`, `exten` (Many2one `connect.exten`), `template` (Many2one `connect.elevenlabs_agent_template`), `transfer_to_agent` (One2many `connect.elevenlabs_agent_transfer`), `has_transfer_tool` (compute).

**Key methods:**

| Method | Description |
|--------|-------------|
| `create`/`write`/`unlink` | Enforce license, sync ElevenLabs agent, manage prompt-version history |
| `_sync_elevenlabs_agent()` | Create on ElevenLabs + persist `agent_uid` |
| `create_elevenlabs_agent()` / `update_elevenlabs_agent()` / `delete_elevenlabs_agent()` | REST calls |
| `_build_conversational_config()` | Build `ConversationalConfig` (agent/asr/tts/conversation + language presets) |
| `_build_platform_settings()` | Build `AgentPlatformSettingsRequestModel` |
| `_compute_prompt_config()` | Inject call-context placeholders (`{{previous_topics}}`, `{{available_extensions}}`) |
| `_compute_built_in_tools()` | Dictionary for system tools (transfer/voicemail/keypad) |
| `compute_agent_tools()` | Return non-system tool IDs |
| `render(request, params=None)` | Emit TwiML `<Connect><Stream url=wss://…/twilio/stream/{agent_uid}/{call_id}/{channel_sid}>` |
| `transfer(channel_sid, exten)` | Twilio REST redirect of current call leg |
| `create_extension()` | Allocate a `connect.exten` row |
| `print_config()` | Debug: dump agent config from ElevenLabs |

Validations: `temperature ∈ [0, 1]`, `stability ∈ [0, 1]`, `speed ∈ [0.7, 1.2]`, `similarity_boost ∈ [0, 1]`.

---

### 3. agent_tool.py — `connect.elevenlabs_agent_tool`, `connect.agent_tool_params` (NEW)

Tool definitions for agents.

**`connect.elevenlabs_agent_tool` fields:** `name` (unique), `tool_id` (ElevenLabs tool id), `synced`, `description`, `tool_type` (`client` / `webhook` / `system`), `path`, `url`, `method` (GET/POST/PATCH/PUT/DELETE), `params` (One2many), `body_params_description`, `response_timeout_secs`, `param_type` (currently `body`), `client_expects_response`, `disable_interruptions`, `voicemail_message`, `use_out_of_band_dtmf`.

**Methods:** `get_tool_url()`, `compute_agent_tools_config()`, `_sync_to_elevenlabs()`, `update_elevenlabs_tool()`, `delete_elevenlabs_tool()`, `remove_all_from_elevenlabs()`, `_sync_system_tool_to_agents()`. System-tool writes fan-out to all agents that reference them.

**`connect.agent_tool_params` fields:** `name`, `data_type` (string/boolean/integer), `required`, `value_type` (`description` / `dynamic_variable` / `constant_value`), `constant_value`, `dynamic_variable`, `description`, `tool` (Many2one).

---

### 4. agent_prompt.py — `connect.elevenlabs_agent_prompt` (NEW)

Prompt-version history. Fields: `name` (`v1`, `v2`, …), `agent` (Many2one), `prompt` (Text).

### 5. agent_template.py — `connect.elevenlabs_agent_template` (NEW)

Starter templates for new agents. Fields: `name`, `system_prompt`. Seed data in `data/agent_templates.xml`.

### 6. agent_transfer.py — `connect.elevenlabs_agent_transfer` (NEW)

Agent-to-agent transfer rules. Fields: `agent` (source), `transfer_to_agent`, `condition`.

### 7. voice.py — `connect.elevenlabs_voice` (NEW)

ElevenLabs voice catalogue. Fields: `voice_id` (unique), `name`, `language`, `accent`, `age`, `gender`, `preview_url`, `preview_audio` (Html, compute), `description`. `get_voices()` pulls from ElevenLabs and deletes absent ones.

### 8. file.py — `connect.elevenlabs_file` (NEW)

TTS audio file generated from text. Fields: `text` (required), `file` (Binary), `filename`, `preview_audio` (Html, compute). Methods: `generate_elevenlabs_voice(text)`, `get_file_path()`, `get_file_url()`. MIME type forced to `audio/mpeg`.

---

### 9. call.py — `_inherit = 'connect.call'`

| Field | Type | Notes |
|---|---|---|
| `elevenlabs_agent` | Many2one (`connect.elevenlabs_agent`) | readonly |
| `elevenlabs_summary` | Html | readonly |
| `elevenlabs_transcript` | Text | compute from recording |
| `elevenlabs_conversation_id` | Char | readonly |
| `elevenlabs_recording_widget` | Html | compute (audio tag) |

**Methods:** `elevenlabs_agent_get_call_data()` (payload for the media bridge: partner/extension/previous-conversation context), `elevenlabs_agent_start_call_event(params)` (model method called by the bridge), `_get_elevenlabs_recording_data()`. Also overrides `_get_recording_data()` to show an icon on agent calls with recordings.

### 10. recording.py — `_inherit = 'connect.recording'`

| Field | Type |
|---|---|
| `elevenlabs_transcript` | Text |
| `elevenlabs_summary` | Text |
| `elevenlabs_media_file` | Binary |
| `elevenlabs_recording_widget` | Html (compute) |
| `list_summary` | Html (compute — prefers ElevenLabs summary) |

Overrides `transcribe_recording()`: if `transcript_provider == 'elevenlabs'` uses ElevenLabs STT (`scribe_v1`, diarized), otherwise falls back to `super()` (OpenAI Whisper).

### 11. callflow.py — `_inherit = 'connect.callflow'`

| Field | Type |
|---|---|
| `elevenlabs_enabled` | Boolean (compute) |
| `prompt_message_file` / `invalid_input_message_file` / `voicemail_prompt_file` | Many2one (`connect.elevenlabs_file`) |
| `prompt_message_widget` / `invalid_input_message_widget` / `voicemail_prompt_widget` | Html (related to preview_audio) |

Constraints auto-regenerate the files on text changes. Overrides `get_prompt_message(gather)`, `get_gather_invalid_input_message(response)`, `get_voicemail_prompt_message(response)` to call `gather.play(<mp3 url>)` / `response.play(…)` when `elevenlabs_enabled`.

### 12. user.py — `_inherit = 'connect.user'`

| Field | Type |
|---|---|
| `elevenlabs_enabled` | Boolean (compute) |
| `voicemail_prompt_file` | Many2one (`connect.elevenlabs_file`) |
| `voicemail_prompt_widget` | Html |

Override `get_voicemail_prompt(response)` to play the generated MP3.

### 13. number.py — `_inherit = 'connect.number'`

Adds `destination='elevenlabs_agent'` and `elevenlabs_agent` Many2one. Overrides `route_call(request)` to call `agent.render(request)` when the DID destination is an agent.

### 14. exten.py — `_inherit = 'connect.exten'`

Adds `dst` selection option `('connect.elevenlabs_agent', 'Agent')` and `agent` Many2one.

---

## Controllers (connect_elevenlabs/controllers/)

### main.py — `ConnectElevenlabsController`

- `POST /connect_elevenlabs/transfer` (http) — header `x-elevenlabs-agent-token`; calls `connect.elevenlabs_agent.transfer(**body)`.
- `POST /connect_elevenlabs/post_call` (http) — validates `elevenlabs-signature` HMAC-SHA256 header + 30-minute timestamp tolerance. Writes `elevenlabs_summary`, `elevenlabs_conversation_id`, fetches conversation audio from `https://api.elevenlabs.io/v1/convai/conversations/{id}/audio`, and creates a `connect.recording` record with transcript + mp3.

`dispatch()` enforces `check_license('connect_elevenlabs', silent=False)`.

### calendar.py — `CalendarController`

All routes `type=jsonrpc` on Odoo 19+, token-gated via `x-elevenlabs-agent-token`:

- `POST /connect_elevenlabs/get_available_slots` — free intervals within 08:00–18:00 for a given user/date/timezone.
- `POST /connect_elevenlabs/create_event` — create a `calendar.event` (returns 201 or 200 if already exists).
- `POST /connect_elevenlabs/get_current_date`
- `POST /connect_elevenlabs/get_meetings` — list meetings for a `partner_id`.
- `POST /connect_elevenlabs/remove_meeting` — unlink a `calendar.event` by id.

---

## Data (connect_elevenlabs/data/)

- `tools.xml` — seed agent tools: system (`language_detection`, `end_call`, `skip_turn`, `play_keypad_touch_tone`, `voicemail_detection`, `transfer_to_agent`) + webhook (`transfer_to_exten`, calendar `get_available_slots` / `create_event` / `get_current_date` / `get_meetings` / `remove_meeting`) with their `connect.agent_tool_params` rows.
- `agent_templates.xml` — reusable system prompts.

## Security (connect_elevenlabs/security/)

- `admin.xml`, `user.xml` — `ir.model.access` for admin/user groups on all new models.
- `webhook.xml` — access rules for `connect.user_connect_webhook` to create/write the models touched by the post-call webhook.

## Views (connect_elevenlabs/views/)

14 files (agent, agent_prompt, agent_template, agent_transfer, agent_tool, agent_tool_params, call, callflow, number, recording, settings, user, voice). `settings.xml` adds an ElevenLabs notebook tab on `connect.settings`.

## Service (connect_elevenlabs/service/)

`main.py` + `twilio_audio_interface.py` — FastAPI WebSocket at `/twilio/stream/{agent_uid}/{call_id}/{channel_sid}` bridging Twilio Media Streams to the ElevenLabs conversational-AI client. `Dockerfile` + `pyproject.toml` describe the deploy artefact.

---

## License

Each model CRUD path and the controller `dispatch` call `self.env['oduist.license'].check_license('connect_elevenlabs', silent=…)`. `settings.py` appends `'connect_elevenlabs'` to `ODUIST_MODULES`. No new SQL migrations required.
