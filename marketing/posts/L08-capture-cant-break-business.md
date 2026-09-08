---
id: L08
title: Capture that can never break your business
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_memory_sale/docs/index.md, connect_memory_sale/docs/events.md, specs/connect_memory.md]
---

## Post

The riskiest part of any "capture everything" feature is the day it throws an exception inside an order confirmation — and your salesperson can't confirm the order. 💥

**Oduist Connect Memory** is written so that day cannot happen:

🧵 Every capture path snapshots the record **before** `super()` and wraps the emission in `try/except`. A failure to build or enqueue an event is logged and swallowed
🛑 It can never roll back a sale order, an invoice posting or a payment reconciliation
📴 No HTTP call inside your transaction — capture writes one row to a local table. If no gateway is running, events simply accumulate
🪪 Even the licence gate degrades to "allow" on any error, so a check can't block a business operation
🎚️ Master switch off? Every path checks it first and returns immediately

The troubleshooting order is documented too: master switch, external partner, licence, then the module logger.

An integration that fails safe is worth more than one that fails loudly. Agree? 👇

#Odoo #Engineering #ERP #AI #Reliability

## Card

```json
{
  "template": "thesis",
  "accent": "purple",
  "kicker": "Oduist Connect · Memory",
  "headline": "The memory can fail.",
  "headline_grad": "The order still commits.",
  "lede": "Capture is *fire-and-forget by construction* — one local row, wrapped, never in the critical path.",
  "tiles": [
    {"sym": "try", "nm": "every path wrapped", "c": "core"},
    {"sym": "pre", "nm": "snapshot before super()", "c": "provider"},
    {"sym": "log", "nm": "failures logged, swallowed", "c": "cyan"},
    {"sym": "0", "nm": "no HTTP in the transaction", "c": "app"},
    {"sym": "lic", "nm": "licence gate fails open", "c": "memory"},
    {"sym": "OK", "nm": "the order still commits", "c": "app", "hero": true}
  ],
  "footer": "ADR-009 · troubleshooting: switch → external partner → licence → logger"
}
```

## Notes

Nuance: the licence gate degrades to "allow" only *on error*. When the check
legitimately returns false, events are dropped — the host operation still
succeeds.
