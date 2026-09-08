---
id: C02
title: Подключить 3CX к Odoo
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_3cx/docs/admin/3cx-setup.md]
---

## Post

"We'd love our calls in Odoo, but we're NOT replacing our 3CX." — heard this a dozen times. Good news: you don't have to. 🔌

**Oduist Connect for 3CX V20** links the two in an afternoon:

✅ Phone rings → the customer's Odoo card pops up
✅ Call ends → it's journaled in the chatter, recording included
✅ Click a number in Odoo → your 3CX dials it

No rip-and-replace. No SIP migration project. Your PBX keeps doing what it does — Odoo finally sees it.

Running 3CX + Odoo separately today? Let's talk. 👇

#3CX #Odoo #Telephony #CTI

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · 3CX",
  "headline": "Keep your 3CX.",
  "headline_grad": "Add Odoo.",
  "lede": "Caller ID lookup, call journal in the chatter and click-to-call — *without replacing your PBX*. Set up in an afternoon.",
  "nodes": [
    {"t": "3CX V20", "s": "your existing PBX", "c": "provider"},
    {"t": "Odoo", "s": "CRM · Helpdesk · Contacts", "c": "app"}
  ],
  "link_label": "Connect",
  "footer": "Contact pop-up on ring · Call log & recordings in Odoo · Click-to-call"
}
```

## Notes

Requires 3CX V20, PRO or AI edition. Free/Basic/SMB are not supported — worth
stating in replies to avoid doomed evaluations.
