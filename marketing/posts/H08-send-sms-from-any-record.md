---
id: H08
title: Send SMS from any Odoo record
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/messages.md, connect_twilio/docs/messaging.md, connect_infobip/docs/admin/infobip-setup.md, connect_bird/docs/admin/bird-setup.md]
---

## Post

The fastest customer update is the one you can send without leaving the record you're already looking at. 📲

In **Oduist Connect** that's four clicks:

1️⃣ Open the record — contact, lead, order, whatever you're working on
2️⃣ **Send SMS** from the action menu
3️⃣ Pick an **Outgoing Number** from your Connect caller IDs
4️⃣ Type, send

What happens next is the part that matters:

📇 The message is stored in the shared ledger and linked to the partner
🚚 It goes out through whichever provider that user is set to — Twilio, Telnyx, Infobip or Bird
📶 Its delivery status updates itself as the carrier reports back
↩️ Replies come back into the same list, against the same contact

No separate SMS tool, no exported contact list, no "which number did we text them from?"

What's the one message your team sends over and over — delivery ETA, appointment reminder, payment due? 👇

#Odoo #SMS #CRM #FieldService #CustomerCommunication

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · SMS Composer",
  "headline": "Send an SMS from",
  "headline_grad": "the record you're on.",
  "lede": "Action menu → outgoing number → text. The message is *stored against the contact* and its status updates itself.",
  "nodes": [
    {"t": "Any Odoo record", "s": "contact · lead · order", "c": "app"},
    {"t": "SMS out", "s": "Twilio · Telnyx · Infobip · Bird", "c": "provider"}
  ],
  "link_label": "Send SMS",
  "footer": "Outgoing number from your Connect caller IDs · replies land on the same contact"
}
```

## Notes

The SMS composer wizard ships in the provider modules (ADR-031), not in core —
the action appears once a messaging provider is installed.
