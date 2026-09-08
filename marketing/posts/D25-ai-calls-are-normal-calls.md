---
id: D25
title: Every AI call is a normal call record
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/ai-agents.md]
---

## Post

Every voice-AI vendor ships a beautiful dashboard. That is precisely the problem: it is one more console your team has to open every morning. 📊

In Oduist Connect an AI call is not a special object living somewhere else:

📞 Calls to an AI agent appear in Connect → Calls like any other call — same list, same filters, same reports
⏺️ With recording enabled, the conversation shows up under Recordings on that same call form
📝 For a Telnyx assistant the row carries the downloaded audio, the conversation transcript and the insight summary together
🚨 When the agent itself fails, an Error tab shows the reason the provider reported — without it, a broken call just looks like a suspiciously short one
🧵 Same contact, same chatter, same history: your CRM reporting never has to know an AI took the call

The vendor console is for debugging the agent. The business record belongs in Odoo, next to the customer it is about.

How many consoles does your team check before the first coffee? 👇

#Odoo #VoiceAI #CRM #CallCenter #AI

## Card

```json
{
  "template": "thesis",
  "accent": "purple",
  "kicker": "Oduist Connect · AI Agents",
  "headline": "An AI call is just",
  "headline_grad": "a call record.",
  "lede": "No separate console: agent calls land in the *same ledger* as every human call, with audio, transcript and summary.",
  "tiles": [
    {"sym": "Ca", "nm": "Call record", "c": "purple", "hero": true},
    {"sym": "Rec", "nm": "Recording", "c": "provider"},
    {"sym": "Tr", "nm": "Transcript", "c": "magenta"},
    {"sym": "Su", "nm": "Summary", "c": "app"},
    {"sym": "Er", "nm": "Error tab", "c": "core"},
    {"sym": "Pa", "nm": "Contact & chatter", "c": "memory"}
  ],
  "footer": "Connect ▸ Calls — human and AI conversations in one history"
}
```

## Notes

Transcript + insight summary on the recording row is the Telnyx path
specifically. Dograh keeps its own workflow-level transcript in the Dograh
dashboard as well — do not claim the Odoo record is the only copy.
