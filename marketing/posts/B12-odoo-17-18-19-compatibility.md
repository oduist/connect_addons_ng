---
id: B12
title: Odoo 17 / 18 / 19 telephony compatibility
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/admin/installation.md, connect_twilio/docs/installation.md]
---

## Post

Three Odoo series. One codebase. Zero "we'll support that next year." 🧬

**Oduist Connect** runs on Odoo **17.0, 18.0 and 19.0**, and it is not three products wearing the same name:

🧾 The **Python source is byte-identical** across the three branches. Where Odoo genuinely behaves differently, the code branches inside the same file — it is never forked per series.
🖼️ Only **XML views and per-series migrations** differ between branches. That is the entire diff.
🔢 **Manifest versions are aligned**: a module at `19.0.1.8.13` is at `18.0.1.8.13` once the change is ported. The tail is the product version; the head only marks the target series.

Why you should care: an upgrade from 17 to 19 does not become a telephony project, and a fix released for one series is a near-empty diff for the others.

Requirements are the same everywhere: `phonenumbers`, `jinja2`, `openai`, plus your provider's SDK.

Which series are you on — and which one are you dreading? 👇

#Odoo #Odoo19 #Telephony #OpenSource #Upgrade

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Compatibility",
  "headline": "Three Odoo series.",
  "headline_grad": "One codebase.",
  "lede": "17.0, 18.0 and 19.0 run *byte-identical Python*. Only views and per-series migrations differ between branches.",
  "tiles": [
    {"sym": "17", "nm": "Odoo 17.0", "c": "provider"},
    {"sym": "18", "nm": "Odoo 18.0", "c": "provider"},
    {"sym": "19", "nm": "Odoo 19.0", "c": "cyan", "hero": true},
    {"sym": "py", "nm": "Identical Python", "c": "core"},
    {"sym": "xml", "nm": "Views per series", "c": "app"},
    {"sym": "ver", "nm": "Aligned versions", "c": "memory"}
  ],
  "footer": "Requires phonenumbers · jinja2 · openai, plus your provider SDK"
}
```

## Notes

`19.0.1.8.13` is an illustrative version string, not a released one. Swap it for
a real current version pair before publishing, or drop the numbers and keep the
rule.
