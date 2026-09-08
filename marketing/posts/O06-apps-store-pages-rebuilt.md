---
id: O06
title: Every module's Apps Store page, rebuilt
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [docs/changelog.md, AGENTS.md]
---

## Post

Nobody evaluates an Odoo module from a wall of grey text and a screenshot from 2019. 🎨

We rebuilt every Oduist Connect page in the Odoo Apps Store in one house style — same structure on all of them, so you can compare modules without re-learning the layout each time.

🧭 One shape per page: what the module does, what it needs, and what it actually adds to your Odoo
🌉 The Accounting, HR, Project and Sales bridges got a page for the first time — small modules that link calls to invoices, employees, tasks and orders by partner
📚 In the same pass the documentation moved into each module's own folder, so a module's store page, its section of the docs site and its in-Odoo guide all come from one place
🔍 Every claim on a page is traced back to the code that implements it. If a feature isn't in the module, it isn't on the page

Unglamorous work. But an evaluation that starts with an honest page ends in fewer surprises for both sides.

What's the fastest way you judge whether a module is worth installing? 👇

#Odoo #OdooApps #ProductDesign #B2BSaaS

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Apps Store",
  "headline": "Every module page,",
  "headline_grad": "rebuilt.",
  "lede": "One house style across the whole range — and a first page for the *Accounting, HR, Project and Sales* bridges.",
  "tiles": [
    {"sym": "AC", "nm": "Accounting", "c": "app", "hero": true},
    {"sym": "HR", "nm": "Employees", "c": "cyan"},
    {"sym": "PRJ", "nm": "Project", "c": "provider"},
    {"sym": "SO", "nm": "Sales", "c": "memory"},
    {"sym": "CRM", "nm": "Leads", "c": "magenta"},
    {"sym": "HD", "nm": "Helpdesk", "c": "core"}
  ],
  "footer": "Same structure on every page · docs and store page from one source"
}
```

## Notes

Time-sensitive: shipped in the 2026-08 changelog. Publish soon — a "we redid
our store pages" post ages badly. If it slips, reframe around the bridge
modules themselves (calls linked to invoices, employees, tasks and orders),
which is evergreen.

Only Accounting, HR, Project and Sales are documented as new pages; CRM and
Helpdesk are on the card as existing bridges, not as new pages.
