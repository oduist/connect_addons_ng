---
id: F04
title: Number matching vs partner matching
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/business-records.md, connect_sale/docs/index.md, connect_hr/docs/index.md, connect_crm/docs/configuration.md, connect_helpdesk/docs/configuration.md]
---

## Post

Most teams evaluating call-to-record linking miss this: there is no single matching rule. There are two, and knowing which one applies explains every "why didn't it link?" ticket. 🧩

**By phone number** — CRM, Helpdesk and HR compare the other party's number against the record's own phone fields. CRM matches open leads, Helpdesk matches open tickets, HR matches an employee's work phone and work mobile.

**By partner** — Sale, Accounting and Project use the contact the core already resolved on the call, then look up that contact's most recent qualifying record: an open order, a posted unpaid customer invoice, an open task.

The practical consequence:

🔢 Number matching works for a caller who has no contact record yet
👤 Partner matching does nothing until the core matches a contact — that's the prerequisite
🧱 Both are provider-agnostic: same behaviour on Twilio, Telnyx, FreeSWITCH, Asterisk, 3CX

Which of the two would fit your data better? 👇

#Odoo #CRM #Telephony #ERP #Integration

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · Bridges",
  "headline": "Two matching models.",
  "headline_grad": "Six bridges.",
  "lede": "CRM, Helpdesk and HR match *by phone number*. Sale, Accounting and Project match *by partner*.",
  "columns": ["By number", "By partner"],
  "rows": [
    {"f": "CRM leads", "m": ["✓", "—"]},
    {"f": "Helpdesk tickets", "m": ["✓", "—"]},
    {"f": "HR employees", "m": ["✓", "—"]},
    {"f": "Sale orders", "m": ["—", "✓"]},
    {"f": "Customer invoices", "m": ["—", "✓"]},
    {"f": "Tasks & projects", "m": ["—", "✓"]}
  ],
  "footer": "Partner matching needs a resolved contact · number matching does not"
}
```

## Notes

Each bridge is licensed separately; without a license the linking silently does
nothing while calls are still recorded.
