---
id: H10
title: WhatsApp Business profile management from Odoo
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_twilio/docs/messaging.md, connect_telnyx/docs/admin/telnyx-setup.md]
---

## Post

Quick question for anyone running WhatsApp Business: what's your sender's quality rating right now? 📉

Most teams don't know, because the answer lives in a portal nobody opens.

**Oduist Connect** puts the WhatsApp sender on an Odoo form:

🏷️ **Business profile** — name, about, address, description, emails, websites, logo. On Telnyx you edit it in Odoo and it's pushed back to the provider
⭐ **Quality rating** — the provider's health score for that sender
📈 **Messaging limit** — your daily messaging tier
🟢 **Status** — online / offline, with the offline reason spelled out
🔗 **Callback URLs** — computed for you, so inbound and status webhooks aren't a copy-paste exercise
⭐ **Default sender** — plus per-user senders, so each rep can message from their own number

Sync imports senders from the account; the profile fields stay in Odoo where the people who care about them already work.

When did you last check your WhatsApp quality rating? Honest answers only 👇

#WhatsApp #Odoo #Twilio #Telnyx #CustomerEngagement

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · WhatsApp Senders",
  "headline": "Your WhatsApp health,",
  "headline_grad": "on an Odoo form.",
  "lede": "Sender profile, quality rating and messaging tier where your team already works — *synced from the provider*, editable and pushed back on Telnyx.",
  "tiles": [
    {"sym": "🏷", "nm": "Profile", "c": "app"},
    {"sym": "⭐", "nm": "Quality rating", "c": "magenta"},
    {"sym": "📈", "nm": "Messaging tier", "c": "cyan"},
    {"sym": "🟢", "nm": "Sender status", "c": "app"},
    {"sym": "🔗", "nm": "Callback URLs", "c": "provider"},
    {"sym": "👤", "nm": "Per-user sender", "c": "purple"}
  ],
  "footer": "Twilio & Telnyx WhatsApp senders · admin-only · Sync imports from the account"
}
```

## Notes

Editing the profile in Odoo and pushing it back is documented for Telnyx. On
Twilio the profile fields are shown on the sender form; treat the push-back
claim as Telnyx-specific in replies.
