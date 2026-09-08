---
id: D20
title: Agent-to-agent transfer by natural-language conditions
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_elevenlabs/docs/agents.md]
---

## Post

Every phone menu asks the caller to classify their own problem. Callers are terrible at it — which is why "press 1 for sales" delivers so many support calls. 🌳

Agent-to-agent transfer replaces the keypad tree with meaning:

🎧 One receptionist agent answers everything and actually listens to the request before routing it
🧭 Each handoff target is a target agent plus a condition written in plain language — "the caller wants pricing or a new order"
🔥 The handover happens warm and mid-conversation: the specialist agent takes over the same call. No re-dial, no "please hold", no repeating the story
🧩 The targets are rows on the agent form in Odoo, editable once the transfer-to-agent tool is attached — changing routing is a text edit, not a dialplan project
🙋 The same agent can still hand off to a human when the caller asks for one

Your routing logic stops being a numbered tree and becomes a set of sentences your team can read.

Still maintaining a five-level phone menu? What would you delete first? 👇

#Odoo #VoiceAI #IVR #CustomerService #AI

## Card

```json
{
  "template": "dialog",
  "accent": "purple",
  "kicker": "Oduist Connect · AI Agents",
  "headline": "Routing by meaning,",
  "headline_grad": "not by keypad.",
  "lede": "Each handoff is a *target agent plus a condition* in plain language — the transfer happens warm, mid-conversation.",
  "bubbles": [
    {"side": "left", "who": "Caller", "text": "\"I got an invoice I don't understand — and I also want to add ten more licences.\""},
    {"side": "right", "who": "Receptionist agent", "text": "\"Let me bring in the colleague who handles billing — staying on the line with you.\""}
  ],
  "badge": "✓ Condition matched: \"caller asks about an invoice\"",
  "footer": "transfer_to_agent · targets and conditions configured in Odoo"
}
```

## Notes

Agent-to-agent transfer requires the `transfer_to_agent` system tool on the
agent; the Transfer targets list only becomes editable then. Human transfer is a
separate tool (`transfer_to_exten`) — keep the two distinct in replies.
