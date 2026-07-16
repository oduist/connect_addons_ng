# 034 — ElevenLabs voice agents as a Twilio add-on

## Problem

The `connect_elevenlabs*` modules (ElevenLabs Conversational-AI voice agents,
plus helpdesk / knowledge / sale tool packs) were written for the **old
monolithic** `connect_addons` generation, where core `connect` bundled Twilio
and owned `connect.callflow` / `connect.number` / `connect.exten` /
`connect.whatsapp_sender` and the Twilio client. In `connect_addons_ng`
(ADR-031) core is technology-agnostic and those models live per-provider in
`connect_twilio` (`connect.twilio.callflow` / `connect.twilio.number` /
`connect.twilio.exten` / `connect.twilio.outgoing_callerid`;
`connect.whatsapp_sender` keeps its name but ships in `connect_twilio`;
`get_client()` is added to `connect.settings` by `connect_twilio`).

The port had to decide where ElevenLabs lands in the provider-separated world.

## Options

1. **Twilio add-on** — `connect_elevenlabs` depends on `connect_twilio`; retarget
   the PBX `_inherit`s to `connect.twilio.*`.
2. **Split** — a provider-agnostic `connect_elevenlabs` (agent/tool/voice/knowledge
   REST + settings) plus a `connect_elevenlabs_twilio` bridge for call routing.

## Decision

**Option 1.** Every call-path feature of the module is Twilio-native:
`agent.render()` emits `<Dial><Sip>` to ElevenLabs' SIP ingress
(`sip.rtc.elevenlabs.io`), `agent.transfer()` calls `client.calls(sid).update()`,
inbound DIDs/WhatsApp senders route to an agent through
`connect.twilio.{number,exten,whatsapp_sender}`, and callflow TTS prompts render
on the Twilio callflow. There is no provider-agnostic call path to preserve, so a
split would create a `connect_elevenlabs` core that cannot place a single call —
plus a fifth module — for no current consumer.

`connect_elevenlabs` therefore depends on `['connect', 'connect_twilio',
'calendar']`. The three PBX `_inherit`s retarget to `connect.twilio.*`; the agent
`exten` M2O points at `connect.twilio.exten`; `is_published` (which lived on the
old monolithic `connect.exten`) is re-added to `connect.twilio.exten` by the
add-on, since `agent.transfer()` and the conversation-initiation payload expose
only published extensions to the AI.

If a second telephony provider ever needs ElevenLabs, Option 2 can be extracted
later; nothing here blocks it.

## Consequences

- ElevenLabs is Twilio-only today (matches reality: the runtime is Twilio SIP
  ingress + ElevenLabs native SIP, no self-hosted media bridge).
- Sub-modules: `connect_elevenlabs_helpdesk` (needs Enterprise `helpdesk`),
  `connect_elevenlabs_knowledge`, `connect_elevenlabs_sale` — all depend on
  `connect_elevenlabs`.
- Integration is webhook-driven (no self-hosted service): a Conversation
  Initiation Client Data webhook (`/connect_elevenlabs/conversation_initiation`,
  agent-token header) supplies per-call dynamic variables, and an HMAC-signed
  post-call webhook (`/connect_elevenlabs/post_call`) logs the conversation as a
  `connect.call` + `connect.recording`.
