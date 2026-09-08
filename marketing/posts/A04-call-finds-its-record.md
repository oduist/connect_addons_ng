---
id: A04
title: Six ways a phone call finds its record in Odoo
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/business-records.md, connect/docs/user/calls.md, connect/docs/admin/installation.md]
---

## Post

Six Odoo records, six different matching rules — and nobody tags a single call by hand. 📎

**Oduist Connect** attaches a call while it is still being processed:

👤 **Contact** — the caller's number is matched against your partners; unknown numbers get a **Create Partner** button.
👷 **Employee** — matched by phone number, against the employee's work and mobile numbers.
🧾 **Invoice** — by customer, to their newest *posted, unpaid customer invoice*. Vendor bills are never matched.
🛒 **Sale order** — by customer, to their most recent order.
✅ **Task** — by customer, to their newest task in an open stage; no open task, and it links the project instead.
🎯 **Lead / 🎫 Ticket** — CRM and Helpdesk bridges, plus **Create Lead** / **Create Ticket** on the call form.

Matching runs once. A call that already points at a record is never re-assigned, so your manual correction survives.

And when AI summaries are on, the summary is posted into that record's chatter.

Which of the six would save your team the most typing? 👇

#Odoo #CRM #Telephony #CTI #Automation

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Bridges",
  "headline": "Six ways a call finds",
  "headline_grad": "its record in Odoo.",
  "lede": "Lead, ticket, order, invoice, task, employee — *matched automatically, once per call*, and never silently re-assigned.",
  "tiles": [
    {"sym": "CRM", "nm": "Leads", "c": "app"},
    {"sym": "HD", "nm": "Tickets", "c": "app"},
    {"sym": "Sal", "nm": "Sale orders", "c": "app"},
    {"sym": "Acc", "nm": "Invoices", "c": "app"},
    {"sym": "Prj", "nm": "Tasks", "c": "app"},
    {"sym": "HR", "nm": "Employees", "c": "app"}
  ],
  "footer": "Call summaries land in the linked record's chatter"
}
```

## Notes

The docs spell out explicit matching rules for HR, Sale, Account and Project
only; CRM and Helpdesk are documented as bridges with **Create Lead** /
**Create Ticket** buttons. Don't state a CRM/Helpdesk matching rule in the
comments without checking `connect_crm/docs/configuration.md` and
`connect_helpdesk/docs/configuration.md` first. Each bridge is licensed
separately from the core.
