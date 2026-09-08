---
id: F12
title: Why no invoice or employee is created from a call
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_account/docs/index.md, connect_hr/docs/index.md, connect/docs/user/business-records.md]
---

## Post

We get asked for it regularly: "Can a call also create the invoice? And the employee record?"

It can. We chose not to. 🙅

In **Oduist Connect**, four bridges create records from a call — lead, ticket, task, sale order. Two deliberately don't:

🧾 **Accounting** is lookup-only. An invoice is an accounting document with tax, sequence and legal consequences. It should not come into existence because someone dialled a number.
👤 **HR** is lookup-only. Employees arrive through onboarding, with a contract behind them — never from an inbound call.
🔒 The Account bridge is scoped tighter still: posted, unpaid *customer* invoices only. Vendor bills and credit notes are never matched.

Every "create" button we don't ship is a class of junk records your finance and HR teams never have to clean up.

Where would you draw that line? 👇

#Odoo #Accounting #HR #ProductDesign #ERP

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · Design",
  "headline": "Four buttons.",
  "headline_grad": "Two deliberate gaps.",
  "lede": "Calls can create a lead, a ticket, a task or a sale order. *Invoices and employees are lookup-only, on purpose.*",
  "columns": ["Create from call", "Lookup only"],
  "rows": [
    {"f": "CRM lead", "m": ["✓", "—"]},
    {"f": "Helpdesk ticket", "m": ["✓", "—"]},
    {"f": "Project task", "m": ["✓", "—"]},
    {"f": "Sale order", "m": ["✓", "—"]},
    {"f": "Customer invoice", "m": ["—", "✓"]},
    {"f": "Employee", "m": ["—", "✓"]}
  ],
  "footer": "Restraint is a feature — fewer junk records to clean up later"
}
```

## Notes

BRAND-type post; the argument is the documented design rationale in the Account
and HR module guides, not a roadmap statement.
