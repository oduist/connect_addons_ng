---
id: D15
title: The agent greets in the contact's Odoo language
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/ai-agents.md, connect_telnyx/docs/admin/telnyx-setup.md]
---

## Post

Your Odoo contact card already knows this customer speaks French. Your phone system usually doesn't. ☎️

Oduist Connect hands that single field to the AI agent:

🌐 One contact matched by phone → the first greeting is prepared in that contact's Odoo language, already localised
🔁 If the caller clearly switches language mid-call, the agent follows
🕵️ Unknown number, or several contacts sharing it → it starts in the configured fallback language instead of guessing
🎛️ Admins can also pin an agent to one fixed language, or ignore the contact entirely and detect from speech
📇 Nothing new to maintain — it is the Language field on the contact record you already keep

No "press 2 for English". No language-selection menu burning fifteen seconds before the conversation starts.

The customer just gets greeted correctly, in the first sentence, by a system that finally read its own database.

Does your phone system know anything your CRM knows? 👇

#Odoo #VoiceAI #CustomerExperience #CRM #AI

## Card

```json
{
  "template": "dialog",
  "accent": "purple",
  "kicker": "Oduist Connect · AI Agents",
  "headline": "It greets callers",
  "headline_grad": "in their language.",
  "lede": "The greeting language comes from the *matched Odoo contact* — no menu, no \"press 2 for English\".",
  "bubbles": [
    {"side": "left", "who": "Caller · number known to Odoo", "text": "\"Allô ?\""},
    {"side": "right", "who": "AI Agent", "text": "\"Bonjour Madame Dupont, merci de votre appel. En quoi puis-je vous aider ?\""}
  ],
  "badge": "✓ Language taken from the contact record in Odoo",
  "footer": "Contact language · caller-switch follow · configurable fallback"
}
```

## Notes

Applies when exactly one contact matches the number; ambiguous matches fall back
to the agent language and no name is used. The Telnyx doc ships Russian and
Polish translations of the standard receptionist greeting — other languages use
the fallback greeting until their Odoo translation is installed. Do not promise
a localised greeting in every language out of the box.
