---
id: B4
title: Choosing an AI voice engine for Odoo
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_elevenlabs/docs/index.md, connect_elevenlabs/docs/agents.md, connect_pipecat/docs/admin/pipecat-setup.md, connect_dograh/docs/admin/dograh-setup.md, connect_livekit/docs/admin/livekit-setup.md, connect_telnyx/docs/admin/telnyx-setup.md]
---

## Post

There is no best AI voice engine. There is the one that matches your telephony and your appetite for running servers. 🤖

**Hosted, fastest to a working agent**
🎙️ **ElevenLabs** — a Twilio add-on. Agents are created and edited in Odoo and synced to your workspace, with automatic prompt versioning, calendar and partner tools, and warm transfer to published extensions.
📡 **Telnyx AI Assistants** — native to Telnyx, managed from Odoo, with personal/company receptionist routing.

**Self-hosted, you run the sidecar**
🧩 **LiveKit Agents** — STT→LLM→TTS or OpenAI Realtime, with contact / CRM / helpdesk tools; agent config is pulled from Odoo at dispatch.
⚡ **Pipecat** — over FreeSWITCH `mod_audio_fork`; pick your own STT, LLM and TTS providers per agent.
🧠 **Dograh** — open-source, drag-and-drop workflow builder, also places outbound campaign calls through your trunks.

One honest limit: Dograh workflows cannot yet transfer to a human.

Hosted or self-hosted — which way is your team leaning? 👇

#VoiceAI #Odoo #ElevenLabs #LiveKit #AI

## Card

```json
{
  "template": "thesis",
  "accent": "purple",
  "kicker": "Oduist Connect · AI Engines",
  "headline": "Five voice engines.",
  "headline_grad": "One Odoo call log.",
  "lede": "Hosted agents that sync from Odoo, or a self-hosted sidecar where you pick every model. *Same recordings, transcripts and summaries.*",
  "tiles": [
    {"sym": "11", "nm": "ElevenLabs", "c": "purple"},
    {"sym": "Tx", "nm": "Telnyx AI", "c": "provider"},
    {"sym": "LK", "nm": "LiveKit Agents", "c": "purple"},
    {"sym": "Pc", "nm": "Pipecat", "c": "purple"},
    {"sym": "Dg", "nm": "Dograh", "c": "purple"},
    {"sym": "Core", "nm": "Odoo tools", "c": "core", "hero": true}
  ],
  "footer": "Hosted or self-hosted · agents answer real numbers and extensions"
}
```

## Notes

Transport constraints to state up front in any evaluation: ElevenLabs requires
`connect_twilio`; Pipecat and Dograh require `connect_freeswitch` with an image
that has `mod_audio_fork`; LiveKit needs its own stack plus a BYO carrier trunk.
Pipecat's documented acceptance target (first audio under 1.4 s) is a
deployment target, not a guarantee — do not quote it as a product metric.
