---
id: I15
title: Restrict who may dial your AI agent
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_elevenlabs/docs/agents.md]
---

## Post

Your AI voice agent has a SIP address. So the security question isn't "what will it say?" — it's **who is allowed to dial it?** 🎙️

When **Oduist Connect** creates an ElevenLabs agent, it registers a virtual SIP phone number so ElevenLabs will accept inbound INVITEs for that agent. The SIP tab (managers only) is where you decide who those INVITEs may come from:

🌐 **Inbound Allowed IPs** — a comma- or newline-separated IP/CIDR list ElevenLabs will accept SIP INVITEs from
🎯 It defaults to Twilio's SIP signalling ranges, so the agent starts locked to the carrier that actually feeds it
⚠️ Leave it empty and any source is allowed — that's a decision, not an accident
🔄 Editing the list re-syncs the virtual number's inbound trunk config automatically
⏳ Pair it with the per-agent limits — max call duration, concurrency limit and daily limit — pushed to the ElevenLabs platform settings

An AI agent with an open SIP ingress and no daily cap is a budget question as much as a security one.

Is your voice agent's ingress restricted today? 👇

#VoiceAI #Odoo #SIP #Security #ElevenLabs

## Card

```json
{
  "template": "diagram",
  "accent": "purple",
  "kicker": "Oduist Connect · ElevenLabs",
  "headline": "Only your carrier",
  "headline_grad": "may dial the agent.",
  "lede": "*Inbound Allowed IPs* on the agent's SIP tab — an IP/CIDR allow-list, defaulted to Twilio's signalling ranges.",
  "nodes": [
    {"t": "Twilio SIP", "s": "signalling ranges", "c": "provider"},
    {"t": "AI agent", "s": "virtual SIP number", "c": "purple"}
  ],
  "link_label": "allow-list only",
  "footer": "Managers-only SIP tab · max duration · concurrency & daily limits"
}
```

## Notes

Empty list = all sources allowed. Say that plainly if someone asks — it's the
shipped behaviour, not a hidden default-deny.
