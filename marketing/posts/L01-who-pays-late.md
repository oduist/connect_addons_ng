---
id: L01
title: Your ERP already knows who pays late
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_memory_sale/docs/payment-digest.md, connect_memory_sale/docs/index.md]
---

## Post

Your accounting already knows which customers pay three weeks late. Your AI assistant usually doesn't — because nobody ever wrote it down in words. 💤

**Oduist Connect Memory** for Sale closes that gap with a scheduled digest:

⏰ An hourly cron walks the customer base in batches and emits one rolled-up **payment-behaviour observation** per customer
📊 Average days late, maximum days late, share of invoices paid late, invoice count and total in company currency — over a configurable look-back window (default 6 months)
🔇 Fewer than 3 qualifying invoices? No event. Not enough signal is better than a misleading one
🔁 Each customer is revisited at most once every 7 days, and the dedup key is per ISO week, so reruns collapse instead of piling up
🎛️ Period, minimum invoices and batch size are plain system parameters you can tune

One stable sentence per customer beats replaying a thousand individual payments.

Would you want that summary on screen before a collections call? 👇

#Odoo #AI #Finance #CustomerMemory #ERP

## Card

```json
{
  "template": "dialog",
  "accent": "purple",
  "kicker": "Oduist Connect · Memory",
  "headline": "How does this one",
  "headline_grad": "actually pay?",
  "lede": "An hourly digest turns reconciled payments into *one durable observation* per customer.",
  "bubbles": [
    {"side": "left", "who": "You · before the call", "text": "\"How does this customer usually pay?\""},
    {"side": "right", "who": "Customer memory", "text": "\"Last 6 months: 8 invoices, avg 5 days late, 38% paid late, max 21 days.\""}
  ],
  "badge": "✓ Memory Sale: Payment Behavior Digest · hourly cron",
  "footer": "Look-back, minimum invoices and batch size are system parameters"
}
```

## Notes

The numbers in the bubble mirror the example digest text from
`payment-digest.md` — they are illustrative, not a customer's real data.
