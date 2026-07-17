# connect_elevenlabs — module spec

ElevenLabs Conversational-AI voice agents for Oduist Connect, as a **Twilio
add-on** (ADR-046). Version `19.0.1.0.0`, depends `['connect', 'connect_twilio',
'calendar']`, external python `elevenlabs` (validated against SDK `2.58.0`).

## Models (owned)

- `connect.elevenlabs_agent` — the agent record. Fields: name, `voice`
  (M2O `connect.elevenlabs_voice`, required), `first_message` (translatable),
  `prompt` + prompt-version history (`connect.elevenlabs_agent_prompt`,
  `active_prompt_version`), `language` + `additional_languages` (M2M res.lang),
  `tools` (M2M `connect.elevenlabs_agent_tool`), `llm`, `temperature`,
  `max_tokens`, TTS knobs (stability/speed/similarity_boost/model), audio formats,
  `agent_uid` (EL agent id), `exten` (M2O `connect.twilio.exten`),
  `el_virtual_number_uid` / `el_inbound_allowed_ips` (SIP routing),
  `template` (M2O `connect.elevenlabs_agent_template`), `transfer_to_agent`
  (`connect.elevenlabs_agent_transfer`). CRUD syncs to ElevenLabs
  (`conversational_ai.agents.create/update/delete`) and registers a virtual SIP
  phone-number (`conversational_ai.phone_numbers`). Key methods:
  `render(request)` → `<Dial><Sip>` to `sip.rtc.elevenlabs.io`;
  `transfer(channel_sid, exten)` via the Twilio client; `build_initiation_payload(...)`
  (dynamic variables for the conversation-initiation webhook — partner, history,
  users directory, published extensions).
- `connect.elevenlabs_agent_tool` + `connect.agent_tool_params` — tool registry
  (system / webhook / client), synced via `conversational_ai.tools`.
- `connect.elevenlabs_agent_prompt`, `connect.elevenlabs_agent_template`,
  `connect.elevenlabs_agent_transfer` — prompt versions, templates, transfer rules.
- `connect.elevenlabs_voice` — voices synced from `voices.get_all()`.
- `connect.elevenlabs_file` — TTS audio (`text_to_speech.convert`), public-read
  for `<Play>` playback of callflow prompts.

## Models (inherited / retargeted for ADR-031)

- `connect.settings` — ElevenLabs credentials (`elevenlabs_api_key` masked via
  `display_*` + `PROTECTED_FIELDS`), `elevenlabs_agent_token`, workspace webhook
  wiring (`_push_elevenlabs_initiation_webhook`, `_push_elevenlabs_post_call_webhook`,
  HMAC secret), `get_elevenlabs_client()`, sync helpers, `transcript_provider`
  `selection_add('elevenlabs')`.
- `connect.call` — `elevenlabs_agent` / `elevenlabs_summary` /
  `elevenlabs_conversation_id` / transcript widgets; `create_from_elevenlabs_inbound`
  (post-call logging → `connect.call` + `connect.recording`).
- `connect.recording` — `transcribe_recording` override: `speech_to_text.convert`
  (`scribe_v1`) + OpenAI summary when `transcript_provider == 'elevenlabs'`.
- `connect.twilio.callflow` — ElevenLabs TTS for prompt / invalid-input / voicemail.
- `connect.twilio.number` — `destination='elevenlabs_agent'` routing.
- `connect.twilio.exten` — `dst` Reference to the agent, **`is_published`** field
  (re-added; absent from ng core).
- `connect.twilio.outgoing_callerid` — used by `render()` caller-id resolution.
- `connect.whatsapp_sender` — `action_route_calls_to_agent(agent)` routes inbound
  WhatsApp calls to an agent via a matching exten.
- `connect.user` — ElevenLabs voicemail prompt (uses `twilio_exten`).

## Controllers (`type='http'`, `auth='public'`, `csrf=False`)

- `/connect_elevenlabs/conversation_initiation` — per-call dynamic variables;
  `x-elevenlabs-agent-token` header.
- `/connect_elevenlabs/post_call` — HMAC (`ElevenLabs-Signature`) verified; logs
  the conversation.
- `/connect_elevenlabs/transfer`, `/connect_elevenlabs/create_partner` — agent
  server tools (token-guarded, run as `connect.user_connect_webhook`).
- `controllers/calendar.py` — 5 calendar tools (get_available_slots, create_event,
  get_current_date, get_meetings, remove_meeting), token-guarded.

## Security

`ir.model.access` XML. `connect.group_admin` — full CRUD; `connect.group_user` —
read (no access to `connect.elevenlabs_agent_template`); `base.group_public` —
read on `connect.elevenlabs_file`; `connect.group_webhook` — read on
agent / tool / params.

## Menu

`menu_connect_elevenlabs` under `connect.menu_connect_root` (seq 50) → Agents,
Agent Templates (admin), Voices, Tools, and a `Configuration` child (admin) →
Settings (via `open_elevenlabs_form`).

## Sub-modules

- `connect_elevenlabs_helpdesk` — helpdesk ticket tools (depends Enterprise
  `helpdesk` via `connect_helpdesk`).
- `connect_elevenlabs_knowledge` — `connect.elevenlabs_knowledge` documents synced
  to `conversational_ai.knowledge_base`, injected into the agent prompt config.
- `connect_elevenlabs_sale` — sale/product/partner agent tools; depends on
  `sale_management` and `website_sale` because the product listing exposes only
  published website products. `get_products` returns `product.product` variant
  IDs for `create_order`.

## Runtime (out of scope for ephemeral env tests)

Live inbound: DID/exten → `connect.twilio.number.render` → `agent.render()`
`<Dial><Sip>` → ElevenLabs native SIP; EL calls the conversation-initiation
webhook for dynamic variables, then the HMAC post-call webhook to log the call.
Requires a real Twilio number + public URL.
