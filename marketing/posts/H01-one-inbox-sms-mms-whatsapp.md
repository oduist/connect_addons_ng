---
id: H01
title: One inbox for SMS, MMS and WhatsApp
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/messages.md, connect_twilio/docs/messaging.md, connect_telnyx/docs/admin/telnyx-setup.md, connect_infobip/docs/admin/infobip-setup.md]
---

## Post

Customers text you on three channels. Your team answers them in three different tabs — and none of it ends up in Odoo. 📥

**Oduist Connect** keeps one message ledger instead:

📨 SMS, MMS and WhatsApp land in the same list, whether they came through Twilio, Telnyx, Infobip or Bird
🔗 The sender's number is matched to a contact automatically — unknown senders can auto-create a partner
🖼️ MMS images and audio play inline on the message record, no download step
📊 Direction, from/to, body, status and partner on every row
💬 WhatsApp conversations post into the partner's chatter next to the calls

Two providers installed? Both menus open the *same* ledger — one history, not two.

Because it's a normal Odoo model, you can filter, group and report on it like anything else.

How many separate messaging tools does your team have open right now? 👇

#Odoo #WhatsApp #SMS #CustomerCommunication #CRM

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Messaging",
  "headline": "Three channels.",
  "headline_grad": "One message ledger.",
  "lede": "SMS, MMS, WhatsApp and RCS from four providers, *stored as one Odoo model* — filterable, reportable, linked to the contact.",
  "tiles": [
    {"sym": "SMS", "nm": "Text", "c": "cyan"},
    {"sym": "MMS", "nm": "Media", "c": "cyan"},
    {"sym": "WA", "nm": "WhatsApp", "c": "app"},
    {"sym": "Tw", "nm": "Twilio", "c": "provider"},
    {"sym": "⇄", "nm": "One ledger", "c": "magenta", "hero": true},
    {"sym": "Tx", "nm": "Telnyx", "c": "provider"},
    {"sym": "RCS", "nm": "Telnyx only", "c": "purple"},
    {"sym": "Ib", "nm": "Infobip", "c": "provider"},
    {"sym": "Bd", "nm": "Bird", "c": "provider"}
  ],
  "footer": "connect.message · shared ledger across every messaging provider"
}
```

## Notes

RCS is Telnyx-only today (see H05). Bird cannot receive inbound messages yet —
platform limitation, covered honestly in H11; don't imply full two-way Bird
messaging in the comments.
