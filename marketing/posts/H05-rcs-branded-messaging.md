---
id: H05
title: RCS branded messaging with SMS fallback
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_telnyx/docs/admin/telnyx-setup.md]
---

## Post

Your SMS arrives as a grey bubble from an eight-digit number nobody recognises. RCS arrives with your brand name on it. 🏷️

**Oduist Connect + Telnyx** brings RCS into Odoo:

🏢 RCS agents are provisioned through Telnyx with Google RBM verification, then synced read-only into **RCS Agents**
✉️ Send from the *RCS Reply* action on a chatter message, or from the composer wizard
📶 Every RCS message can carry an **SMS fallback** from a sender number you configure — the customer gets the message either way
📥 Inbound RCS lands on the same messaging webhook and in the same message ledger as your SMS and WhatsApp
🎯 Recipient fields use the standard Odoo phone control

Straight answer on scope: v1 sends RCS **text with SMS fallback**. Rich cards and carousels aren't composed from Odoo yet, and RCS is Telnyx-only among our providers.

Is RCS live for your customers' carriers yet? Curious what coverage looks like in your market 👇

#RCS #Odoo #Telnyx #BusinessMessaging #CX

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · Telnyx RCS",
  "headline": "Branded messages,",
  "headline_grad": "with an SMS safety net.",
  "lede": "RCS agents synced from Telnyx, sent from the chatter or the composer — with a *configurable SMS fallback* when RCS isn't available.",
  "columns": ["SMS", "RCS"],
  "rows": [
    {"f": "Verified brand identity", "m": ["—", "✓"]},
    {"f": "Delivered to any handset", "m": ["✓", "—"]},
    {"f": "Automatic SMS fallback", "m": ["—", "✓"]},
    {"f": "Inbound into the ledger", "m": ["✓", "✓"]},
    {"f": "Send from the chatter", "m": ["✓", "✓"]},
    {"f": "Rich cards & carousels", "m": ["—", "—"]}
  ],
  "footer": "RCS is available through the Telnyx integration · text + SMS fallback in v1"
}
```

## Notes

"Rich cards & carousels" is a — / — row on purpose: the docs list it as a known
v1 limitation, and saying so beats being caught out in the comments.
