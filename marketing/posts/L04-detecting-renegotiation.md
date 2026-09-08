---
id: L04
title: Detecting renegotiation
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_memory_sale/docs/events.md, connect_memory_sale/docs/index.md]
---

## Post

A confirmed order that keeps changing is a renegotiation. Your ERP faithfully stores the new number — and quietly forgets that it moved. 📉

**Oduist Connect Memory** for Sale remembers the movement:

✍️ Edit an order that is already in `sale` state and it emits a `state_change` event describing what changed
📸 Tracked values — total, untaxed amount, currency, order date, validity date, commitment date, shipping address — are snapshotted **before** the write, so the event carries real old → new pairs
🧾 The order-line command list is parsed into per-line add / update / delete diffs: quantity, unit price, discount, subtotal
📝 The result reads like a sentence: *"S00021 (Acme Corp) edited: amount_total: 900.0 -> 1100.0; Product A.price_unit: 300 -> 350"*
🏷️ Tagged `signal:renegotiation`, so the pattern is queryable across your whole customer base

Which accounts get renegotiated after confirmation, and by how much? That's a question your data can finally answer.

Do you track post-confirmation changes today — or just the final total? 👇

#Odoo #Sales #AI #ERP #RevenueOps

## Card

```json
{
  "template": "diagram",
  "accent": "purple",
  "kicker": "Oduist Connect · Memory",
  "headline": "The total changed.",
  "headline_grad": "That's the story.",
  "lede": "Edits after confirmation become a *state_change* event with old → new diffs, per field and per line.",
  "nodes": [
    {"t": "Confirmed sale order", "s": "edited after confirmation", "c": "app"},
    {"t": "Memory event", "s": "old → new, line by line", "c": "memory"}
  ],
  "link_label": "signal:renegotiation",
  "footer": "Snapshot before super() · per-line add / update / delete diffs"
}
```

## Notes

The example sentence is lifted from `events.md`. Note for replies: only free-form
edits key on a timestamp; lifecycle transitions (confirm / cancel / lock) key on
the record and label instead.
