---
id: F14
title: Manual corrections always win
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/business-records.md, connect_sale/docs/configuration.md, connect_project/docs/configuration.md, connect_hr/docs/configuration.md]
---

## Post

The fastest way to make people distrust an automation: let it overwrite the fix they just made. 🤖

So the rule across every **Oduist Connect** bridge is one line — **a call that already points at a record is never re-assigned.**

✍️ Move a call to the right invoice, task or lead by hand, and it stays there
🚫 The automatic matcher only writes into an empty field — it never corrects you
🔓 **Unlink** detaches a call from a record without deleting either one
1️⃣ Matching runs once per call, right after the call is registered — not on a loop that re-litigates old decisions
🐞 Matches are logged, so a wrong link can be explained instead of argued about

Automation you can override is automation people leave switched on. Automation that argues back gets disabled within a month.

Which automation in your stack did your team quietly turn off? 👇

#Odoo #Automation #ERP #ProductDesign #CRM

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Linking",
  "headline": "The matcher fills gaps.",
  "headline_grad": "It never argues.",
  "lede": "A call that already points at a record is *never re-assigned* — automatic matching writes only into an empty field.",
  "tiles": [
    {"sym": "✍", "nm": "Manual wins", "c": "app", "hero": true},
    {"sym": "1×", "nm": "Runs once", "c": "cyan"},
    {"sym": "∅", "nm": "Empty only", "c": "cyan"},
    {"sym": "🔓", "nm": "Unlink", "c": "provider"},
    {"sym": "🐞", "nm": "Logged", "c": "memory"},
    {"sym": "🗑", "nm": "Nothing deleted", "c": "core"}
  ],
  "footer": "Same rule in the CRM, Helpdesk, HR, Sale, Account and Project bridges"
}
```

## Notes

Unlink is available on the call form for each bridge (and clears both task and
project for the Project bridge).
