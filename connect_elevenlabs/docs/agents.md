# Agents, Tools & Voices

This page covers building an ElevenLabs agent and everything it depends on:
prompts, templates, tools, transfers, voices and text-to-speech files, plus how
to route calls to an agent.

## Agents

Manage agents under **Connect ▸ ElevenLabs ▸ Agents** (`connect.elevenlabs_agent`).
Creating, editing or deleting an agent in Odoo synchronises the change to your
ElevenLabs workspace over the API — there is no need to touch the ElevenLabs
dashboard.

!!! info "Live sync to ElevenLabs"
    On **create**, the module calls `conversational_ai.agents.create`, stores the
    returned `agent_uid`, pushes the full config, and registers a **virtual SIP
    phone number** so ElevenLabs will accept inbound SIP INVITEs for the agent.
    On **write** it calls `conversational_ai.agents.update`; on **delete** it
    removes the agent and its virtual number. Every create/write first checks the
    `connect_elevenlabs` license.

### Prompt tab

| Field | Description |
|-------|-------------|
| **Template** (`template`) | Optional starting point; selecting one copies the template's system prompt into `prompt`. |
| **Prompt Version** (`active_prompt_version`) | Pick a previously saved version to restore its text into the prompt. |
| **First Message** (`first_message`) | The agent's opening line. Translatable — per-language translations become ElevenLabs *language presets* for the languages you list under **Additional Languages**. |
| **Prompt** (`prompt`) | The system prompt. |

!!! note "Automatic prompt versioning"
    Every time you change **Prompt**, the module snapshots the new text as a new
    `connect.elevenlabs_agent_prompt` record (`v1`, `v2`, …) and marks it the
    active version. Use **Prompt Version** to roll back to an earlier snapshot.

The prompt sent to ElevenLabs is augmented at build time with two blocks that
reference dynamic variables: a *last conversation summary* (`{{previous_topics}}`)
and *call transfer information* listing `{{available_extensions}}`. These are
filled per call by the conversation-initiation webhook (see below).

### Conversation tab

| Field | Description |
|-------|-------------|
| **Voice** (`voice`, required) | The ElevenLabs voice, from the synced voice library. |
| **Tools** (`tools`) | The tools this agent can call (see [Tools](#tools)). |
| **Transfer targets** (`transfer_to_agent`) | Shown when the `transfer_to_agent` system tool is attached: one row per target agent plus a natural-language **condition**. |
| **Language** / **Additional Languages** | Primary language and the extra languages (from `res.lang`) for which first-message translations are exported as presets. |
| **Turn timeout**, **Silence end-call timeout** | Conversation timing knobs. |
| **Max duration (s)**, **Agent concurrency limit**, **Daily limit** | Call limits pushed to ElevenLabs platform settings (`-1` = unlimited). |
| **Exten** (`exten_number`) | The internal extension routed to this agent (created with the **Extension** button — see [Routing](#routing-calls-to-an-agent)). |

### LLM / TTS tab

| Field | Description |
|-------|-------------|
| **LLM** (`llm`) | The model the agent reasons with — OpenAI GPT, Google Gemini, Anthropic Claude, or an ElevenLabs-hosted open model. Default `gpt-5.2`. |
| **Max Tokens** (`max_tokens`) | `-1` means no cap; a positive value limits the LLM prediction length. |
| **Output / User Input Audio Format** | Codec/sample rate (default `ulaw_8000`, the Twilio telephony format). |
| **Temperature** | `0.0`–`1.0` creativity. |
| **Model** (`model`) | The ElevenLabs TTS model (Turbo / Flash v2 / v2.5). |
| **Stability** | `0.0`–`1.0`. |
| **Speed** | `0.7`–`1.2`. |
| **Similarity Boost** | `0.0`–`1.0`. |

!!! warning "Validated ranges"
    Temperature (0–1), stability (0–1), similarity boost (0–1) and speed
    (0.7–1.2) are enforced by model constraints; out-of-range values raise a
    validation error on save.

### SIP tab (managers only)

| Field | Description |
|-------|-------------|
| **ElevenLabs Virtual Number ID** (`el_virtual_number_uid`) | Read-only. The ElevenLabs `phone_number` entity registered under the agent, used as the SIP routing identifier when no real DID is attached (e.g. an extension routed straight to the agent). |
| **Inbound Allowed IPs** (`el_inbound_allowed_ips`) | Comma- or newline-separated IP/CIDR list ElevenLabs will accept SIP INVITEs from. Defaults to Twilio's SIP signalling ranges. Empty allows all sources. Editing this re-syncs the virtual number's inbound trunk config. |

### Header buttons

- **Extension** — creates a `connect.twilio.exten` pointing at this agent so it
  can be dialled internally and routed to.
- **Print** — developer helper that logs the agent's live ElevenLabs config.

## Agent Templates

Manage under **Connect ▸ ElevenLabs ▸ Agent Templates**
(`connect.elevenlabs_agent_template`, admin only). A template is just a named
reusable **system prompt**. Selecting a template on a new agent copies its
`system_prompt` into the agent's prompt. The module ships an *Appointment
Assistant* template wired for the calendar tools.

## Tools

Manage under **Connect ▸ ElevenLabs ▸ Tools** (`connect.elevenlabs_agent_tool`).
Tools are what let an agent *do* things during a call. There are three types.

| Type | Meaning |
|------|---------|
| **System** | Built-in ElevenLabs behaviours (end call, language detection, voicemail detection, transfer to agent, keypad tones). Managed as part of the agent config, not as standalone remote tools. |
| **Webhook** | An HTTP call ElevenLabs makes during the conversation — usually back into Odoo. Created/updated in the ElevenLabs tool registry (`conversational_ai.tools`). |
| **Client** | A tool executed on the client side; may block the conversation until a response is returned. |

!!! info "Automatic tool sync"
    Creating a non-system tool syncs it to ElevenLabs and stores the returned
    `tool_id`; editing updates it; deleting removes it. Editing a **system** tool
    instead re-pushes every agent that uses it (system tools live in agent
    config). Use **SYNC TOOLS** on the settings form to reconcile all tools at
    once. Names must match `^[a-zA-Z0-9_-]{1,64}$` and are unique.

### Tool fields

| Field | Description |
|-------|-------------|
| **Name**, **Description** | The tool identifier and the natural-language instructions the LLM uses to decide when to call it. |
| **Tool Type** | `system` / `webhook` / `client`. |
| **Path** / **URL** | For webhook tools: an internal Odoo path (resolved against the API URL) **or** an external URL. |
| **Method** | `GET` / `POST` / `PATCH` / `PUT` / `DELETE` (default `POST`). |
| **Parameters** (`params`) | The arguments the tool takes (see below). |
| **Parameters Description** | Extra guidance for populating the body. |
| **Response Timeout** | Seconds (webhook: 5–120; client: 1–30). |
| **Expects Response** (client) | Whether the conversation blocks for the client reply. |
| **Disable interruptions** | Prevent the user from interrupting while the tool runs. |
| **Voicemail Message** | (for the `voicemail_detection` system tool) message to play when voicemail is detected. |
| **Out of Band DTMF** | (for the `play_keypad_touch_tone` system tool) use out-of-band DTMF. |

### Tool parameters

Each parameter (`connect.agent_tool_params`) has a **data type** (string /
boolean / integer), a **required** flag and a **value type** that decides where
its value comes from:

| Value type | Source of the value |
|------------|---------------------|
| **LLM Prompt** (`description`) | The LLM fills it from the conversation, guided by the parameter's description. |
| **Dynamic Variable** | Filled from a per-call dynamic variable (e.g. `channel_sid`, `partner_phone`, `call_id`) supplied by the conversation-initiation webhook or SIP headers. |
| **Constant Value** | A fixed value. |

Webhook tools that call Odoo automatically include the
`x-elevenlabs-agent-token` header so the Odoo controller can authenticate the
call.

### Seed tools shipped with the module

**System tools:** `language_detection`, `end_call`, `skip_turn`,
`play_keypad_touch_tone`, `voicemail_detection`, `transfer_to_agent`.

**Webhook tools (call back into Odoo):**

| Tool | Endpoint | Purpose |
|------|----------|---------|
| `transfer_to_exten` | `/connect_elevenlabs/transfer` | Transfer the live call to a company extension (e.g. "connect me to a human"). |
| `create_partner` | `/connect_elevenlabs/create_partner` | Create a `res.partner` for an unknown caller and link it to the call. |
| `calendar_get_available_slots` | `/connect_elevenlabs/get_available_slots` | Free business-hours slots (08:00–18:00) for a user on a date. |
| `calendar_create_event` | `/connect_elevenlabs/create_event` | Book a calendar event (deduped by user + start/stop). |
| `calendar_get_current_date` | `/connect_elevenlabs/get_current_date` | Current server date/time. |
| `calendar_get_meetings` | `/connect_elevenlabs/get_meetings` | List a partner's meetings. |
| `calendar_remove_meeting` | `/connect_elevenlabs/remove_meeting` | Cancel a meeting by event id. |

All of these Odoo endpoints are authenticated by the agent token — see
[Webhooks & Security](webhooks-security.md).

## Agent-to-agent transfer

When an agent carries the `transfer_to_agent` system tool, its **Transfer
targets** list becomes editable. Each row names a **target agent** and a
**condition** describing when to hand the conversation over. These are exported
into the system tool's config so ElevenLabs performs a warm agent-to-agent
transfer mid-conversation.

## Voices

See [Configuration ▸ Voices](configuration.md#voices). Voices are synced from the
ElevenLabs voice library and referenced by agents (per-agent **Voice**) and by
the settings-level **Selected Voice** used for TTS file generation.

## Text-to-speech files (call-flow & voicemail prompts)

`connect.elevenlabs_file` holds ElevenLabs TTS audio (MP3) generated from text
with the **Selected Voice** (`text_to_speech.convert`, model
`eleven_multilingual_v2`). These files are public-read so Twilio can fetch them
with `<Play>`.

When the integration is enabled, the Twilio call-flow prompts and per-user
voicemail greetings are voiced by ElevenLabs instead of Twilio `<Say>`:

- **`connect.twilio.callflow`** — the **prompt**, **invalid-input** and
  **voicemail** messages each get a generated TTS file, regenerated whenever the
  text changes (or in bulk via **REGENERATE PROMPTS**). At render time the
  call-flow `<Play>`s the file URL, falling back to the base `<Say>` behaviour on
  any error or when the integration is disabled.
- **`connect.user`** — a user's voicemail greeting is rendered to a TTS file and
  played back the same way.

## Routing calls to an agent

An agent answers only calls that reach it through Twilio. There are three ways to
route:

=== "Phone number (DID)"

    On a **Connect ▸ Twilio ▸ Numbers** record, set **Destination** to *Agent*
    and pick the **ElevenLabs agent**. Inbound calls to that number render TwiML
    that dials ElevenLabs' SIP ingress for the agent
    (`connect.twilio.number.render` → `agent.render()`).

=== "Extension"

    Use the **Extension** button on the agent form to create a
    `connect.twilio.exten` whose `dst` references the agent. Dialling that
    extension routes the call to the agent. When no real DID is attached, the
    agent's registered **virtual number** is used as the SIP identifier.

=== "WhatsApp calls"

    `connect.whatsapp_sender.action_route_calls_to_agent(agent)` creates (or
    updates) an extension matching the sender's E.164 number so inbound WhatsApp
    calls on that number are answered by the agent.

!!! note "Published extensions drive transfers"
    The `is_published` flag on `connect.twilio.exten` (re-added by this module)
    controls which extensions the agent is told about. Only **published**
    extensions appear in the `{{available_extensions}}` dynamic variable and are
    valid targets for the `transfer_to_exten` tool. Mark the extensions you want
    the AI to be able to transfer to as **Published**.
