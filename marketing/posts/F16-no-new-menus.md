---
id: F16
title: No new menus — integrating without clutter
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_hr/docs/index.md, connect_sale/docs/index.md, connect_account/docs/index.md, connect_project/docs/index.md, connect_crm/docs/index.md, connect_helpdesk/docs/index.md]
---

## Post

Six modules. Zero new menu items. That was a design goal, not an oversight. 🧭

The **Oduist Connect** business bridges — CRM, Helpdesk, HR, Sale, Accounting, Project — add no menu of their own. Everything shows up where people already work:

🔘 A **Calls** smart button on the lead, ticket, employee, order, invoice, task and project
📑 A notebook page on the call form with the linked record and an **Unlink** action
📊 Optional columns on the Connect call list, off unless you enable them
⚙️ Settings live on the shared Connect settings form, not in six new places
🧩 Install one bridge or all six — the navigation your users learned doesn't move

An integration that reorganises your menus is a migration project. One that doesn't is just a feature that appeared.

How many apps in your Odoo do people never open? 👇

#Odoo #UX #ERP #Integration #ProductDesign

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Bridges",
  "headline": "Six bridges.",
  "headline_grad": "No new menus.",
  "lede": "Linked calls appear as *smart buttons and tabs on records you already use* — the navigation stays exactly where your team left it.",
  "tiles": [
    {"sym": "🎯", "nm": "CRM", "c": "app"},
    {"sym": "🎫", "nm": "Helpdesk", "c": "cyan"},
    {"sym": "👤", "nm": "HR", "c": "provider"},
    {"sym": "🛒", "nm": "Sale", "c": "memory"},
    {"sym": "🧾", "nm": "Account", "c": "core"},
    {"sym": "✅", "nm": "Project", "c": "purple"},
    {"sym": "☎", "nm": "Calls button", "c": "magenta", "hero": true},
    {"sym": "📑", "nm": "Call tab", "c": "cyan"},
    {"sym": "⚙", "nm": "Shared settings", "c": "provider"}
  ],
  "footer": "Install one bridge or all six — the menu tree never changes"
}
```

## Notes

Contradiction with the plan: the brief said "5 of 6 bridges add no menu items".
Verified by grep — **none** of connect_crm, connect_helpdesk, connect_hr,
connect_sale, connect_account, connect_project defines a `menuitem`, and each
module guide states it adds no menu of its own. The post says six of six.
