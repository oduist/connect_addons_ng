---
id: O05
title: All modules move to BSL 1.1
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/admin/licensing.md, docs/changelog.md]
---

## Post

"Source-available" too often means: you may look, the trial is two weeks, and then we call you. 📜

Every Oduist Connect module is under the **Business Source License 1.1**. Concretely, that means:

🔓 The source is published in a public repository — read it, modify it, have your partner or a freelancer adapt it for your instance
🧪 Evaluation, development and staging use is free. Always
⏱️ Installing a module starts a **30-day production trial automatically**. No registration, no form, no sales call
🏷️ A commercial licence is per Odoo instance, bound to that instance's UID, and bought from inside Odoo
📆 Every released version carries a **Change Date**. On it, that version becomes LGPL-3.0-or-later and the restrictions end

And if a trial lapses, only that module's own features stop. The rest of your Odoo — and every other licensed Connect module — keeps running. Nothing else is blocked or degraded.

BSL restricts use, not modification. We'd rather be explicit about that than vague.

Would BSL pass your procurement review? Genuinely curious. 👇

#Odoo #OpenSource #BSL #Licensing

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Licensing",
  "headline": "Source you can read.",
  "headline_grad": "A trial you don't ask for.",
  "lede": "Business Source License 1.1 across every module: *free for dev and staging*, 30 days of free production, then a per-instance licence.",
  "tiles": [
    {"sym": "BSL", "nm": "1.1", "c": "core", "hero": true},
    {"sym": "SRC", "nm": "Public repo", "c": "app"},
    {"sym": "30d", "nm": "Auto trial", "c": "cyan"},
    {"sym": "1:1", "nm": "Per instance", "c": "provider"},
    {"sym": "CD", "nm": "Change date", "c": "memory"},
    {"sym": "L3", "nm": "Then LGPL", "c": "magenta"}
  ],
  "footer": "Every module ships its own LICENSE file · trial lapse affects that module only"
}
```

## Notes

Time-sensitive: the move shipped in the 2026-07 changelog. As written the post
is evergreen (it explains the licence rather than announcing the switch), so it
can run at any time; add "we moved" framing only if published soon.

Expect licence-purist pushback in comments. Stick to the documented facts:
BSL restricts use, not modification, and each version opens under
LGPL-3.0-or-later on its Change Date.
