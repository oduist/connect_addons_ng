---
id: L02
title: A durable AI memory of every customer
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_memory/docs/user/memory.md, connect_memory_sale/docs/index.md, specs/connect_memory.md]
---

## Post

Nobody has time to write a CRM note after every email. So the notes don't get written, and two years later the account history lives in three people's heads. 🧠

**Oduist Connect Memory** builds the memory from the work itself, not from extra data entry:

✉️ Real external correspondence — emails and chatter comments with an outside author or recipient — captured on the chatter of *any* document
🧾 With the Sale add-on: order creation, confirmations and cancellations, posted invoices and refunds, reconciled payments
📈 Plus an hourly payment-behaviour digest per customer
🔗 Everything is keyed to the **commercial partner**, so a contact, their company and their orders end up in one memory
🔘 A **Memory events** smart button on the contact shows the count and every captured item with the record it came from
♻️ Deduplicated on a stable key plus a content hash — an edit creates a new event, a replay doesn't

It's built from your daily work, so it's never out of date.

What would you ask a memory like that before your next customer call? 👇

#Odoo #AI #CRM #CustomerMemory #ERP

## Card

```json
{
  "template": "thesis",
  "accent": "purple",
  "kicker": "Oduist Connect · Memory",
  "headline": "The account history",
  "headline_grad": "writes itself.",
  "lede": "Captured from *real work* — correspondence and business events, keyed by commercial partner.",
  "tiles": [
    {"sym": "Em", "nm": "external emails", "c": "cyan"},
    {"sym": "Ch", "nm": "chatter comments", "c": "cyan"},
    {"sym": "SO", "nm": "sale order lifecycle", "c": "app"},
    {"sym": "Inv", "nm": "posted invoices & refunds", "c": "app"},
    {"sym": "Pay", "nm": "reconciled payments", "c": "app"},
    {"sym": "Dg", "nm": "payment-behavior digest", "c": "memory", "hero": true}
  ],
  "footer": "Memory events smart button on every contact · deduplicated by content hash"
}
```

## Notes

Internal notes and system messages are never captured — worth stating in the
first reply, it is the most common question.
