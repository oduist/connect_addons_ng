---
id: M04
title: What happens when a licence lapses
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/admin/licensing.md, connect_sale/docs/configuration.md, connect_hr/docs/configuration.md, connect_account/docs/configuration.md]
---

## Post

The nightmare scenario people imagine: a licence lapses and the ERP falls over on a Monday morning. 😰

That's not what happens here, and the behaviour is documented rather than implied.

If a module's trial ends and no commercial licence is active for the instance:

🟢 **Only that module's own features stop working.** The rest of your Odoo installation is untouched — nothing else is blocked or degraded
🟢 Other Connect modules that *are* licensed keep working normally
🔔 A licence banner appears in the interface saying the module needs a licence
🧾 On the bridge modules — Sale, HR, Accounting, Project — calls are still recorded in the ledger; what stops is the automatic linking to an order, employee or invoice, and the AI summary posted to that record's chatter
⚠️ A direct user action tells you why: the Sale Order button raises *"Connect Sale license is not activated!"* rather than failing quietly
🧰 Two ways out: buy a licence for the module, or uninstall it

Degrade, don't detonate. Your telephony history stays yours either way.

What's your team's policy on renewal reminders — calendar, or the software telling you? 👇

#Odoo #SoftwareLicensing #BusinessContinuity #ERP #Telephony

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · Licence Lapse",
  "headline": "The trial ended.",
  "headline_grad": "Odoo keeps running.",
  "lede": "Only the unlicensed module's own features stop. *Calls are still recorded*; what pauses is the linking and the summary posting.",
  "columns": ["Lapsed", "Licensed"],
  "rows": [
    {"f": "Rest of your Odoo works", "m": ["✓", "✓"]},
    {"f": "Other licensed modules work", "m": ["✓", "✓"]},
    {"f": "Calls still recorded (bridges)", "m": ["✓", "✓"]},
    {"f": "Auto-link to order / invoice", "m": ["—", "✓"]},
    {"f": "AI summary to the chatter", "m": ["—", "✓"]},
    {"f": "The module's own features", "m": ["—", "✓"]}
  ],
  "footer": "Buy a licence or uninstall the module · a banner tells you which"
}
```

## Notes

The "calls are still recorded" row is documented for the bridge modules
(connect_sale / hr / account / project), where the licence gate is a silent skip.
Don't generalise it to every module — a provider module's own features do stop.
