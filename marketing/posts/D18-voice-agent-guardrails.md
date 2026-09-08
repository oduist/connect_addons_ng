---
id: D18
title: Cost and abuse guardrails for voice agents
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_elevenlabs/docs/agents.md]
---

## Post

A runaway voice agent doesn't crash. It keeps talking — and keeps billing. 💸

Before you point a public phone number at an AI, set the boring limits. On an ElevenLabs agent in Oduist Connect they are plain fields on the agent form, pushed straight to the platform:

⏳ Max duration — a hard cap in seconds on any single conversation, so one stuck call cannot run all afternoon
🚦 Agent concurrency limit — how many calls this agent may hold at once, which is also your blast radius when something goes wrong
📅 Daily limit — the ceiling that stops a bad day turning into a bad invoice
🤐 Turn timeout and silence end-call timeout — hang up on dead air instead of paying to listen to it
🛡️ Inbound Allowed IPs — the agent's SIP ingress only accepts INVITEs from the ranges you list

Every limit accepts -1 for unlimited. Deliberately choosing unlimited is a fine engineering decision. Discovering it on an invoice is not.

Which of these would you set first on day one? 👇

#Odoo #VoiceAI #FinOps #AI #Telephony

## Card

```json
{
  "template": "thesis",
  "accent": "purple",
  "kicker": "Oduist Connect · AI Agents",
  "headline": "Voice agents need",
  "headline_grad": "guardrails, not trust.",
  "lede": "Duration, concurrency and daily caps are *fields on the agent form* — set before the number goes public.",
  "tiles": [
    {"sym": "MAX", "nm": "Max duration (s)", "c": "purple", "hero": true},
    {"sym": "CNC", "nm": "Concurrency limit", "c": "magenta"},
    {"sym": "DAY", "nm": "Daily call limit", "c": "provider"},
    {"sym": "TOK", "nm": "Max LLM tokens", "c": "app"},
    {"sym": "SIL", "nm": "Silence end-call", "c": "memory"},
    {"sym": "IP", "nm": "Inbound allowed IPs", "c": "core"}
  ],
  "footer": "-1 = unlimited · limits pushed to the platform on save"
}
```

## Notes

No cost figures anywhere — the docs give none. Inbound Allowed IPs is a
managers-only field on the SIP tab and defaults to Twilio's SIP signalling
ranges; empty allows all sources.
