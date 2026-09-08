---
id: I09
title: No Connect role, no web phone
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/admin/security.md]
---

## Post

A warehouse user who will never make a call still loaded the softphone widget on every page — and it quietly asked the PBX who they were. That's the kind of thing you only notice in a browser network tab. 🔍

**Oduist Connect** closed it at the source. For an internal Odoo user who belongs to none of the Connect groups:

📵 The provider bootstrap RPCs answer "not enabled", so no softphone widget registers and the browser does no PBX lookups on page load
🫥 The Connect app and every provider submenu are absent from the apps menu
🔢 Calls / Messages smart buttons are hidden on partners, leads, employees, orders, invoices, tasks and tickets — their counts are computed with `sudo()`, so before this gate they rendered for everyone and only failed on click
🚧 And a direct URL still returns an `AccessError` — the menu gate is convenience, the access rules are the answer

Less JavaScript, fewer surprise requests, a cleaner UI for people who never touch the phone.

How many of your users load features they'll never use? 👇

#Odoo #Security #WebRTC #Performance #ERP

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · Security",
  "headline": "No Connect role?",
  "headline_grad": "No phone, no lookups.",
  "lede": "Users outside the Connect groups see *no trace* of telephony — not even in the network tab.",
  "columns": ["No Connect group", "Connect User"],
  "rows": [
    {"f": "Connect app in the menu", "m": ["—", "✓"]},
    {"f": "Calls / Messages smart buttons", "m": ["—", "✓"]},
    {"f": "Web phone registers", "m": ["—", "✓"]},
    {"f": "PBX lookups on page load", "m": ["—", "✓"]},
    {"f": "Direct URL opens a Connect page", "m": ["—", "✓"]},
    {"f": "Own user preferences readable", "m": ["✓", "✓"]}
  ],
  "footer": "Menu gate + ir.model.access + record rules — all three, always"
}
```

## Notes

Keep the "counts computed with sudo()" detail — it explains *why* the gate was
needed and reads as honest engineering rather than marketing.
