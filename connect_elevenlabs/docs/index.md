# Oduist Connect ElevenLabs — Administrator Guide

`connect_elevenlabs` adds [ElevenLabs](https://elevenlabs.io) Conversational-AI
voice agents to the Oduist Connect telephony platform for Odoo. It ships as a
**Twilio add-on** (ADR-046): inbound calls that arrive on a Twilio number or
extension are handed off to ElevenLabs' native SIP ingress, where a
conversational agent answers, uses tools that call back into Odoo (partner
lookup, calendar, extension transfer, …), and posts a transcript and summary
back to Odoo when the call ends.

Because it builds on top of Twilio, the module does **not** define its own
numbering plan. Instead it retargets the Twilio PBX-configuration models
(`connect.twilio.number`, `connect.twilio.exten`, `connect.twilio.callflow`,
`connect.twilio.outgoing_callerid`) to add an `elevenlabs_agent` routing
destination, and it owns a set of ElevenLabs-specific models under the
`connect.elevenlabs_*` namespace (agents, prompts, templates, tools, transfers,
voices, TTS files).

## What this module provides

| Area | Capability |
|------|------------|
| **AI agents** | ElevenLabs conversational agents created, updated and deleted from Odoo (`connect.elevenlabs_agent`), fully synced to the ElevenLabs workspace on save |
| **Prompts** | System prompt with automatic version history, reusable agent templates, per-agent first message with per-language translations |
| **Voices & models** | Voices synced from the ElevenLabs voice library, choice of LLM (OpenAI / Gemini / Claude / open models), TTS model, and TTS tuning (stability, speed, similarity boost) |
| **Tools** | System tools (end call, language detection, voicemail detection, transfer, keypad tones), webhook tools that call Odoo (create partner, transfer to extension, calendar), and client tools |
| **Routing** | A phone number or extension routed directly to an agent; inbound WhatsApp calls routed to an agent; call transfer from the agent back to a published extension |
| **Post-call** | HMAC-verified post-call webhook that logs the conversation as a `connect.call` plus a `connect.recording` carrying the transcript and summary |
| **Transcription** | Optional ElevenLabs Speech-to-Text (`scribe_v1`) as a transcript provider for recordings, with an OpenAI summary |
| **TTS prompts** | ElevenLabs text-to-speech audio for Twilio call-flow prompts, invalid-input and voicemail messages, and per-user voicemail greetings |

## Dependencies and prerequisites

The manifest declares `depends = ['connect', 'connect_twilio', 'calendar']` and
the external Python dependency `elevenlabs`.

- A running Odoo instance with the core `connect` module **and** `connect_twilio`
  installed and configured (a working Twilio account, at least one Twilio number,
  SIP/voice routing). ElevenLabs rides on top of Twilio, so Twilio must work
  first — see the Twilio administrator guide.
- The Odoo `calendar` application (used by the built-in calendar agent tools).
- The `elevenlabs` Python package in the Odoo environment (validated against SDK
  `2.58.0`).
- An ElevenLabs account with an API key that has Conversational-AI access.
- **A publicly reachable HTTPS URL for Odoo.** ElevenLabs delivers per-call and
  post-call data over webhooks; the module also pushes webhook URLs built from
  the core **API URL** into your ElevenLabs workspace settings.

!!! info "Licensed module"
    ElevenLabs is a licensed Oduist module. Creating or updating an agent, and
    rendering the routing TwiML at call time, all check the `connect_elevenlabs`
    license. An invalid or expired license blocks agent creation and plays a
    "trial period is over" message instead of connecting the call. See
    [Maintenance ▸ Licensing](maintenance.md#licensing).

## Guide contents

1. [Installation](installation.md) — Python dependency, module install, hooks,
   co-installation with Twilio.
2. [Account Configuration](configuration.md) — ElevenLabs API key, enabling the
   integration, voices, sync actions, and the webhook token.
3. [Agents, Tools & Voices](agents.md) — building agents, prompts, templates,
   tools, transfers, and TTS files.
4. [Webhooks & Security](webhooks-security.md) — webhook routes, the agent
   token, HMAC post-call verification, and access groups.
5. [Maintenance](maintenance.md) — licensing, transcription, routing internals,
   and troubleshooting.

!!! info "Menu location"
    Everything lives under the **Connect ▸ ElevenLabs** submenu of the Connect
    app: **Agents**, **Agent Templates** (admin), **Voices**, **Tools**, and a
    **Configuration ▸ Settings** entry (admin). Administrative screens require
    the **Connect Administrator** group (`connect.group_admin`).
