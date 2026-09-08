---
id: L06
title: Internal conversations are never captured
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_memory_sale/docs/index.md, connect_memory/docs/user/memory.md, specs/connect_memory.md]
---

## Post

"So it reads everything my team writes to each other?" 🙅

No. And that's not a setting someone can flip — it's the gate every capture path runs through.

**Oduist Connect Memory** only captures real correspondence with an **external** party:

📤 An email to a customer, or their reply in the chatter — captured
🤐 An internal note between colleagues — ignored
🤖 System and log messages — ignored
🏢 Records for one of your own companies, or for a partner linked to an internal employee — silently skipped
🎚️ And above all of it a master switch: while *Enable memory capture* is off, nothing is written at all

The same `_memory_is_external` check gates the sales side too, so an internal order or an employee expense never reaches the memory either.

The scope of an AI feature should be a rule in the code, not a promise in a slide.

Would your team use an assistant that can read customer threads but not internal ones? 👇

#Odoo #AI #Privacy #CRM #ERP

## Card

```json
{
  "template": "comparison",
  "accent": "purple",
  "kicker": "Oduist Connect · Memory",
  "headline": "External only.",
  "headline_grad": "By design.",
  "lede": "A single gate — *master switch on* **and** *partner is external* — decides what is ever remembered.",
  "columns": ["Ignored", "Remembered"],
  "rows": [
    {"f": "Email to a customer", "m": ["—", "✓"]},
    {"f": "Customer's chatter reply", "m": ["—", "✓"]},
    {"f": "Internal note between colleagues", "m": ["✓", "—"]},
    {"f": "System / log messages", "m": ["✓", "—"]},
    {"f": "Order for one of your own companies", "m": ["✓", "—"]},
    {"f": "Invoice to an employee-linked partner", "m": ["✓", "—"]}
  ],
  "footer": "mail.thread._memory_is_external · master switch off = nothing captured"
}
```

## Notes

Card columns read as "which bucket does this fall into" — the highlighted right
column is *Remembered*. Check the rendered PNG reads that way before publishing.
