---
id: H06
title: Auto-create contacts from inbound texts
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/admin/core-setup.md, connect/docs/user/messages.md, connect_twilio/docs/messaging.md, connect_bird/docs/admin/bird-setup.md, connect_infobip/docs/admin/infobip-setup.md]
---

## Post

An unknown number texts your business line. Someone reads it, someone answers it, and three weeks later nobody can find who it was. 🕵️

Message Configuration fixes that in about a minute.

In **Oduist Connect**, per inbound number, you set:

📱 **Number** — which of your numbers this rule applies to
🎯 **Destination** — the model the message should create or look up (a contact, for example)
🧾 **Default Values** — a dict of field values stamped onto every record created that way (source, tag, salesperson, country…)

Then: an incoming message from a known number is linked to that contact automatically. From an unknown one, a partner is created, and the conversation is attached to it from the very first reply.

Same mechanism on Twilio, Telnyx, Infobip and Bird. And if you run CRM, the auto-installed `connect_crm_twilio` bridge routes incoming messages to leads instead.

Do you want inbound texts becoming contacts automatically — or reviewed by a human first? 👇

#Odoo #SMS #CRM #Automation #ContactManagement

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Message Configuration",
  "headline": "A text from an",
  "headline_grad": "unknown number.",
  "lede": "One rule per inbound number: destination model plus *default field values* — and the stranger becomes a contact with the conversation already attached.",
  "nodes": [
    {"t": "Inbound SMS / WhatsApp", "s": "sender not in your database", "c": "cyan"},
    {"t": "res.partner", "s": "created with default values", "c": "app"}
  ],
  "link_label": "Message Configuration",
  "footer": "Admin-only · Twilio · Telnyx · Infobip · Bird · CRM leads via connect_crm_twilio"
}
```

## Notes

Message Configuration is an admin-only model in every provider module. The
`default_values` field is a Python dict literal, not free text.
