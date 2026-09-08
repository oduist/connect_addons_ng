---
id: D17
title: Turn-taking and endpointing for voice agents
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_telnyx/docs/admin/telnyx-setup.md]
---

## Post

0.1 seconds. That is the endpointing plan a voice platform can ship by default — and it is exactly why the agent finishes your sentences for you. 😬

Dictate an order number and it starts answering after the third digit.

Turn-taking is a separate set of dials from the transcription model: the model decides nothing about when your turn ended. In Oduist Connect you set them per agent:

⏱️ Wait Before Speaking — the silence it sits through before replying (default 0.4 s)
✂️ Pause Without Punctuation — 1.0 s, the one that keeps the agent out of a pause taken mid-thought
📝 Pause After Punctuation — 0.3 s once the sentence is clearly finished
🔢 Pause After Numbers — 0.6 s while digits are being dictated
🤫 Caller Silence Timeout — 60 s by default, because the platform never ends a conversation on its own

Agent talks over people? Raise them. Feels sluggish? Lower them. That is the entire tuning loop, and it takes one test call per change.

Worse phone experience: an AI that interrupts, or one that pauses awkwardly? 👇

#Odoo #VoiceAI #ConversationDesign #Telnyx #AI

## Card

```json
{
  "template": "thesis",
  "accent": "purple",
  "kicker": "Oduist Connect · AI Agents",
  "headline": "Stop the AI finishing",
  "headline_grad": "your sentences.",
  "lede": "Turn-taking is *tuned, not inherited* — five values decide when the caller's turn ended.",
  "tiles": [
    {"sym": "0.4s", "nm": "Wait before speaking", "c": "purple"},
    {"sym": "1.0s", "nm": "Pause · no punctuation", "c": "magenta", "hero": true},
    {"sym": "0.3s", "nm": "Pause · punctuation", "c": "provider"},
    {"sym": "0.6s", "nm": "Pause after numbers", "c": "app"},
    {"sym": "60s", "nm": "Caller silence timeout", "c": "memory"},
    {"sym": "0.1s", "nm": "Platform default plan", "c": "core"}
  ],
  "footer": "Per-agent endpointing · Connect ▸ Telnyx ▸ AI Assistants"
}
```

## Notes

All five values are the documented defaults for Telnyx assistants in Connect.
The 0.1 s figure is the plan Telnyx itself ships — attribute it that way, not as
a competitor benchmark. Caller Silence Timeout accepts 10–14,400 s.
