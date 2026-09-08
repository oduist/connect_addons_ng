---
id: F10
title: Every quotation call logged on the quotation
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_sale/docs/configuration.md, connect_sale/docs/index.md]
---

## Post

A quotation goes through four calls before it's signed. Odoo usually remembers the discount and none of the conversations. 🧾

**Oduist Connect Sale** attaches the call to the order automatically. When a call is recorded and its contact is resolved, Connect finds that customer's most recent **open** order — Quotation, Quotation Sent or Sales Order. Cancelled orders never match.

📞 A **Calls** smart button on the order opens every call about it
📄 A **Sale Order** page on the call form shows the link, with an **Unlink** button when it's wrong
🖱️ No order yet? The **Sale Order** button opens a new one, pre-filled with the caller — and back-links it to the call on save
🔎 Partner phone and mobile become search fields on quotations and sales orders
🤖 With AI summaries on, each call summary is posted to the order's chatter

Renegotiating a quote six weeks later becomes reading, not remembering.

How many calls does one of your quotations really take? 👇

#Odoo #Sales #CRM #Quotation #Telephony

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Sale",
  "headline": "Four calls,",
  "headline_grad": "one quotation, one record.",
  "lede": "Calls are attached to the customer's most recent *open* order — Quotation, Quotation Sent or Sales Order.",
  "tiles": [
    {"sym": "📝", "nm": "Quotation", "c": "cyan"},
    {"sym": "📤", "nm": "Sent", "c": "cyan"},
    {"sym": "✅", "nm": "Sales order", "c": "app", "hero": true},
    {"sym": "✗", "nm": "Cancelled", "c": "core"},
    {"sym": "☎", "nm": "Calls button", "c": "provider"},
    {"sym": "🤖", "nm": "Summary", "c": "purple"}
  ],
  "footer": "Matched by partner · manual links are never overwritten"
}
```

## Notes

"Four calls" is a rhetorical figure, not a measured average — do not turn it into
a statistic in comments.
