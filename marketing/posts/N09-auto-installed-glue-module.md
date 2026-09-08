---
id: N09
title: The auto-installed glue module pattern
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_crm_twilio/docs/index.md, connect_crm_twilio/models/message_configuration.py, specs/decisions/031-provider-model-separation.md]
---

## Post

One of our modules is 8 lines of Python. It has no models, no views, no security rules, no menus and no settings. It is also load-bearing. 🧷

`connect_crm_twilio` exists to answer one question: where does "route an inbound SMS to a CRM lead" live?

🚫 Not in `connect_crm` — the CRM bridge must stay provider-agnostic; it knows nothing about Twilio
🚫 Not in `connect_twilio` — the Twilio module must not depend on CRM being installed
✅ So it lives in a third module that depends on both, adds one value to one selection field, and does nothing else
🤖 `auto_install: True` — it appears by itself the moment both parents are present, and you never install or upgrade it directly

Odoo's addon system makes this pattern cheap, and it keeps every module's dependency list honest.

The cost is real though: this is an N×M problem. Every provider × every app pairing is a potential glue module, and the list only grows.

Where's your threshold — at what point does the glue deserve to be a real module? 👇

#Odoo #SoftwareArchitecture #Python #ModularDesign #CRM

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Modules",
  "headline": "Eight lines of Python.",
  "headline_grad": "Zero models.",
  "lede": "A glue module keeps both parents honest: *the CRM bridge stays provider-agnostic, the provider stays CRM-agnostic.*",
  "nodes": [
    {"t": "connect_crm + connect_twilio", "s": "neither may depend on the other", "c": "provider"},
    {"t": "connect_crm_twilio", "s": "one selection value, nothing else", "c": "app"}
  ],
  "link_label": "auto_install",
  "footer": "No models, no views, no security, no menus — and the N×M growth is the price"
}
```

## Notes

"8 lines" = the whole `models/message_configuration.py` body. If the file grows,
change the number rather than rounding it.
