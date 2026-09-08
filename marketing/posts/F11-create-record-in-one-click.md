---
id: F11
title: Create a record in one click from a call
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/business-records.md, connect_sale/docs/configuration.md, connect_project/docs/configuration.md, connect_helpdesk/docs/configuration.md]
---

## Post

Someone calls who isn't in the system yet. The old workflow: hang up, open the right app, retype the number, hope you got it right. 🖱️

In **Oduist Connect** the call form has the button instead:

🎯 **Create Lead** · **Create Ticket** · **Create Task** · **Create Sale Order**
👤 The new record opens pre-filled with the caller as customer, and the caller's number when there's no contact yet
🔗 It is back-linked to the call on save — no second step to remember
🔁 The buttons are idempotent: press one again and it opens the record that already exists, instead of creating a duplicate
🔍 Some of them retry the automatic match first, so an existing lead or ticket is re-used rather than duplicated

Two buttons are deliberately absent — but that's a separate post.

Which of the four would your team hit most often? 👇

#Odoo #CRM #Helpdesk #Sales #Productivity

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Call form",
  "headline": "One click",
  "headline_grad": "from call to record.",
  "lede": "Lead, ticket, task or sale order — pre-filled with the caller, back-linked on save, and *idempotent* on the second press.",
  "tiles": [
    {"sym": "🎯", "nm": "Lead", "c": "app"},
    {"sym": "🎫", "nm": "Ticket", "c": "cyan"},
    {"sym": "✅", "nm": "Task", "c": "provider"},
    {"sym": "🛒", "nm": "Sale order", "c": "memory"},
    {"sym": "🔁", "nm": "No duplicates", "c": "magenta", "hero": true},
    {"sym": "🔗", "nm": "Back-linked", "c": "purple"}
  ],
  "footer": "Each button needs its module's active license"
}
```

## Notes

The create buttons raise an explicit license error when the module's license is
inactive — unlike the silent automatic matching.
