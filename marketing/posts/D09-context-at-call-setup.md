---
id: D09
title: The agent reads the customer's file before it says hello
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_elevenlabs/docs/maintenance.md, connect_elevenlabs/docs/agents.md, connect/docs/user/ai-agents.md]
---

## Post

Blunt engineering truth: an AI voice agent knows nothing about your caller. It's a model on a phone line. 🤷

So we tell it — before it speaks. In **Oduist Connect**, the moment a call is routed to the agent, ElevenLabs calls one webhook back into Odoo and gets the call's context as dynamic variables:

👤 The matched contact — but only when **exactly one** Odoo contact holds that number, and the agent must still ask the caller to confirm the name
🧠 A summary of the previous conversation with the same caller
👥 The internal users directory
🔀 The list of **published** extensions it's allowed to transfer to
🌍 A language override, so the greeting is prepared in the contact's Odoo language

If that webhook fails, it returns empty variables — the agent still answers, just without context. Degrade, don't crash.

The result: the caller doesn't spell their name, their number, or their history for the third time this month.

Would you rather your AI greeted callers by name — or asked every time? 👇

#Odoo #VoiceAI #CX #AIAgents

## Card

```json
{
  "template": "diagram",
  "accent": "purple",
  "kicker": "Oduist Connect · Call Context",
  "headline": "It reads the file",
  "headline_grad": "before it says hello.",
  "lede": "At call setup Odoo hands the agent the contact, the previous-conversation summary, the user directory and the *allowed* transfer targets.",
  "nodes": [
    {"t": "Inbound call", "s": "number or extension", "c": "cyan"},
    {"t": "Odoo", "s": "contact · history · extensions", "c": "app"},
    {"t": "AI Agent", "s": "greets with context", "c": "purple"}
  ],
  "link_label": "conversation initiation",
  "footer": "One webhook, token-authenticated · empty variables on failure, never an error"
}
```

## Notes

Careful with the name claim: per `connect/docs/user/ai-agents.md` the agent
*may use* the matched contact's name but must ask the caller to confirm it, and
does not guess when several contacts share the number.
