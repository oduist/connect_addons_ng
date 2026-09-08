---
id: D19
title: The published-extension allowlist
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_elevenlabs/docs/agents.md, connect_elevenlabs/docs/maintenance.md]
---

## Post

Security question nobody asks their voice-AI vendor: when your agent transfers a call, what actually stops it dialling the CEO? 🔐

If the answer is "we told it not to in the prompt", that is not a control. That is a request.

In Oduist Connect the answer is an allowlist:

✅ Every extension carries a Published flag, and only published extensions are exposed to the agent
📋 They are injected per call into the {{available_extensions}} dynamic variable — the agent cannot name a target it was never given
🚫 Unpublished extensions are not valid targets for the transfer tool, no matter how creatively a caller phrases the request
👤 Publishing is an admin action on an Odoo record: reviewable, auditable, and revocable in one click
🧯 It is closed by default — "agent can't transfer, no published extension" is the documented first thing to check, which is the correct failure direction

Prompt instructions are suggestions to a language model. An allowlist is a boundary in your data.

How does your setup decide who the AI is allowed to reach? 👇

#Odoo #VoiceAI #Security #AI #Telephony

## Card

```json
{
  "template": "comparison",
  "accent": "purple",
  "kicker": "Oduist Connect · AI Agents",
  "headline": "The AI transfers",
  "headline_grad": "only where allowed.",
  "lede": "Extensions are hidden from the agent unless *explicitly published* — a data boundary, not a prompt rule.",
  "columns": ["Unpublished", "Published"],
  "rows": [
    {"f": "Dialled internally by staff", "m": ["✓", "✓"]},
    {"f": "Sent in available_extensions", "m": ["—", "✓"]},
    {"f": "Valid transfer-tool target", "m": ["—", "✓"]},
    {"f": "Can be named by the agent", "m": ["—", "✓"]},
    {"f": "Needs an admin to enable", "m": ["—", "✓"]}
  ],
  "footer": "is_published on the extension · closed by default"
}
```

## Notes

The flag is `is_published` on `connect.twilio.exten`, re-added by
`connect_elevenlabs`. "Dialled internally by staff" is unaffected by the flag —
publishing only controls what the AI is told about.
