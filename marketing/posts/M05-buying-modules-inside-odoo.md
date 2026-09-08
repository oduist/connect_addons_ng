---
id: M05
title: Buying modules from inside Odoo
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/admin/licensing.md]
---

## Post

Counting the steps between "we want this module" and "it's licensed" is a decent proxy for how a vendor thinks about your time. ⏱️

For Oduist Connect, it's four, and none of them leave Odoo:

1️⃣ Open **Connect → Configuration → License**
2️⃣ Review the installed Oduist modules and their current status — trial, licensed, expired
3️⃣ Hit **Buy**: Odoo opens the Oduist payment link for the modules you selected and for your instance
4️⃣ After payment the instance receives a signed licence token bound to its Instance UID, and the status flips from trial to licensed

Two more things on that form:

🔄 **Update Licence / Pricing** re-checks every installed Oduist module and reports what it found — modules checked, modules licensed, your instance registration number — then refreshes prices and versions. A failed check raises an error dialog, not a silent shrug.
📬 Optional subscriptions (security alerts, onboarding, product news) are **off by default**; enabling one shares your notification email with us.

No quote-request form, no waiting on a PDF. Pricing lives at oduist.com/pricing.

What's the worst "request a quote" experience you've had this year? 👇

#Odoo #SoftwareProcurement #Telephony #SaaS #ITBuying

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Licence Configuration",
  "headline": "Buy the module",
  "headline_grad": "without leaving Odoo.",
  "lede": "Configuration → License → *Buy*. Pay, and the instance receives a signed token bound to its Instance UID — status flips from trial to licensed.",
  "nodes": [
    {"t": "Connect → License", "s": "installed modules & status", "c": "app"},
    {"t": "Oduist checkout", "s": "signed token for your instance", "c": "provider"}
  ],
  "link_label": "Buy",
  "footer": "Update Licence / Pricing re-checks every module · pricing at oduist.com/pricing"
}
```

## Notes

No prices in the post text or the card — the pricing page is the only figure
source. Subscriptions are opt-in and independent of licensing; keep that framing.
