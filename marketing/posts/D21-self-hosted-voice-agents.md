---
id: D21
title: Self-hosted AI voice agents
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_pipecat/docs/admin/pipecat-setup.md, connect_dograh/docs/admin/dograh-setup.md, connect_livekit/docs/admin/livekit-setup.md]
---

## Post

"We can't stream customer conversations into somebody else's AI cloud." Fair enough. Then don't. 🏠

Oduist Connect ships three self-hosted routes to AI voice agents, all configured from Odoo:

🧱 Pipecat — a sidecar next to your own FreeSWITCH. Audio rides your media path over WSS, and you supply the API key for every STT, LLM and TTS provider an agent uses
🧩 Dograh — open-source, self-hostable voice AI with a visual workflow builder, answering extensions on your FreeSWITCH and dialling out over your trunks
🎛️ LiveKit — a self-hosted WebRTC + SIP + recording stack with the agent worker running on your hardware, on top of your own carrier trunk

The common thread: your servers, your provider keys, your recordings, your Odoo call history. The AI vendor becomes a component you can swap on a Tuesday rather than the platform you built on.

That is also the honest trade — you now run infrastructure. Some teams want that; many regulated ones have no choice.

Is "where does the audio go" on your procurement checklist yet? 👇

#Odoo #VoiceAI #SelfHosted #OpenSource #AI

## Card

```json
{
  "template": "comparison",
  "accent": "purple",
  "kicker": "Oduist Connect · AI Agents",
  "headline": "Run the voice AI",
  "headline_grad": "on your own metal.",
  "lede": "Pipecat, Dograh and LiveKit — *your servers, your provider keys*, one Odoo control surface.",
  "columns": ["Vendor cloud", "Self-hosted"],
  "rows": [
    {"f": "Media path on your servers", "m": ["—", "✓"]},
    {"f": "Your own STT/LLM/TTS keys", "m": ["—", "✓"]},
    {"f": "Swap providers per agent", "m": ["—", "✓"]},
    {"f": "Runs on your hardware", "m": ["—", "✓"]},
    {"f": "Recordings in the Odoo ledger", "m": ["✓", "✓"]},
    {"f": "Configured from Odoo", "m": ["✓", "✓"]}
  ],
  "footer": "Pipecat · Dograh · LiveKit — sidecars you deploy yourself"
}
```

## Notes

Self-hosted here means the media path and the agent runtime — the STT/LLM/TTS
providers are still external SaaS unless the customer runs local models. Do not
imply the AI models themselves are on-premise.
