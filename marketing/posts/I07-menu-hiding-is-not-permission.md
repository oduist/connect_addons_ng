---
id: I07
title: Menu hiding is not a permission
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/admin/security.md]
---

## Post

"We removed the menu, so they can't get in." 🙃

That sentence has ended more security reviews than it should. Hiding a menu changes what a user *finds*. It changes nothing about what they can *fetch* — a bookmark, a pasted URL or a restored last action goes straight to the record.

**Oduist Connect** does both, and keeps them clearly separated:

🙈 The UX layer: the Connect app and its provider submenus are gated, Calls/Messages smart buttons disappear from partners, leads, orders and tickets, and the web phone never registers
🔐 The security layer: `ir.model.access` rows and record rules
🚧 A user with no Connect group who navigates directly to a Connect page gets an `AccessError` — from the access rules, not from the missing menu

If someone is meant to have access, the fix is to grant Connect User — not to show them the menu again.

How many of your "restricted" screens are actually restricted? 👇

#Odoo #Security #AccessControl #ERP

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Security",
  "headline": "Hiding a menu is UX.",
  "headline_grad": "Access rules are security.",
  "lede": "Connect ships both layers — and *never* mistakes one for the other.",
  "tiles": [
    {"sym": "Mn", "nm": "app menu gated", "c": "cyan"},
    {"sym": "Btn", "nm": "smart buttons hidden", "c": "cyan"},
    {"sym": "Ph", "nm": "web phone doesn't load", "c": "cyan"},
    {"sym": "ACL", "nm": "ir.model.access", "c": "core"},
    {"sym": "RR", "nm": "record rules", "c": "core"},
    {"sym": "403", "nm": "AccessError on direct URL", "c": "magenta", "hero": true}
  ],
  "footer": "Grant connect.group_user to users who are meant to have access"
}
```

## Notes

Nuance worth keeping for replies: an internal user can still read their own
`res.users` record; only the PBX user records stay unreadable.
