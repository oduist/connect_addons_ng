---
id: M03
title: Per-instance licensing and the Instance UID
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/admin/licensing.md]
---

## Post

You duplicate production into a staging database on Friday. On Monday, someone asks why the licence banner is back. 🧬

Here's the mechanic behind it, before it surprises you.

On first use, an Oduist Connect module generates a unique **Instance UID** for the database. A commercial licence is issued for — and bound to — that specific UID: **one licence per Odoo instance**.

So:

🧬 Copy the database, and the copy gets a **new UID**
🚚 Move to a new instance, same thing — the licence has to be re-issued for it
🧪 That's usually fine: non-production use (evaluation, development, staging) is free under BSL 1.1, so your copy doesn't need a production licence to exist
🔁 **Update Licence / Pricing** in Odoo re-checks every installed module and reports which are licensed, plus the instance registration number
🛒 Real migrations are handled by re-issuing, not by re-buying blindly — talk to us before you cut over

Not legal advice; the `LICENSE` file in each module is the binding text.

How many copies of your production database exist right now? Be honest 👇

#Odoo #SoftwareLicensing #DevOps #ITGovernance #Telephony

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Licensing",
  "headline": "One licence,",
  "headline_grad": "one Instance UID.",
  "lede": "The module generates a unique Instance UID on first use; the licence token is *bound to it*. Copy the database and the copy gets a new UID.",
  "nodes": [
    {"t": "Your Odoo instance", "s": "unique Instance UID", "c": "app"},
    {"t": "Signed licence token", "s": "issued for that UID", "c": "provider"}
  ],
  "link_label": "Bound to",
  "footer": "Non-production copies are free under BSL 1.1 · re-issue on migration"
}
```

## Notes

"Talk to us before you cut over" is a process offer, not a licensing promise —
the doc only states that a new UID requires the licence to be re-issued.
