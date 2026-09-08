---
id: F15
title: Ringing vs hung up — two moments
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_crm/docs/configuration.md, connect_helpdesk/docs/configuration.md, connect_sale/docs/index.md, connect_account/docs/configuration.md]
---

## Post

Linking a call to a record and creating a record from a call look like the same feature. They happen at opposite ends of the call — and mixing them up is how integrations produce garbage. 🕐

**While the call is live** (`process_call_event`): **Oduist Connect** attaches what already exists — the open lead, the open ticket, the employee, the customer's open order, invoice or task. It has to be now, because the point is showing the agent who is calling *before* they answer.

**When the call has fully ended** (`register_call`): auto-creation runs. Only here is "answered" or "missed" a fact rather than a guess, and only here can the rule that depends on it be applied correctly.

⚡ Live: link, never create
🏁 Ended: create, only if no record is linked yet
🎯 Result: no lead invented for a call that was answered in two seconds

Same event stream, two moments, two jobs.

Ever been burned by an integration that acted too early? 👇

#Odoo #SoftwareArchitecture #CRM #Telephony #Integration

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Architecture",
  "headline": "Link while ringing.",
  "headline_grad": "Create after hang-up.",
  "lede": "Live events attach *existing* records; creation waits until the call ends, when answered vs missed is a fact.",
  "nodes": [
    {"t": "Ringing", "s": "link existing record", "c": "cyan"},
    {"t": "Hung up", "s": "create if none linked", "c": "app"}
  ],
  "link_label": "one call, two moments",
  "footer": "process_call_event · register_call"
}
```

## Notes

The HR, Sale, Account and Project bridges only do the linking half — creation
rules (with answered/missed toggles) exist in CRM and Helpdesk.
