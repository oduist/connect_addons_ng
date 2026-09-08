---
id: B5
title: 3CX vs Odoo-native telephony — keep both
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_3cx/docs/admin/3cx-setup.md, connect/docs/user/business-records.md]
---

## Post

An afternoon: download an XML file from Odoo, upload it to the 3CX Admin Console. The next external call already shows the Odoo contact name on the agent's screen. 🖥️

That is the whole 3CX story in **Oduist Connect** — nobody replaces anything.

📇 **At call arrival** — 3CX asks Odoo who is calling and shows the name, with a link to the partner form.
🧾 **At call end** — the call is journaled into Connect: direction, answered or missed, duration, agent, queue.
➕ **On request** — an agent creates an Odoo contact for an unknown caller from the 3CX client.
🖱️ **Click-to-call** — a phone number in Odoo opens the 3CX Web Client with the number ready.

3CX keeps numbering, routing and phones. Odoo finally gets the data — and the bridges then attach those calls to leads, tickets, orders and invoices.

What it will not do: no web phone inside Odoo (3CX allows no third-party WebRTC), and no SMS.

Running both side by side today? 👇

#3CX #Odoo #CTI #Telephony #CRM

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · 3CX",
  "headline": "You don't replace 3CX.",
  "headline_grad": "You just add Odoo.",
  "lede": "A generated CRM template turns your PBX into a source of Odoo data — *contact pop, call journal and click-to-call*.",
  "columns": ["3CX alone", "3CX + Connect"],
  "rows": [
    {"f": "Keeps 3CX numbering & phones", "m": ["✓", "✓"]},
    {"f": "Odoo contact name on ring", "m": ["—", "✓"]},
    {"f": "Call journal inside Odoo", "m": ["—", "✓"]},
    {"f": "Click-to-call from Odoo", "m": ["—", "✓"]},
    {"f": "Calls on leads, tickets, invoices", "m": ["—", "✓"]},
    {"f": "Create Odoo contacts from 3CX", "m": ["—", "✓"]},
    {"f": "Web phone inside Odoo", "m": ["—", "—"]}
  ],
  "footer": "3CX V20, PRO or AI edition · server-side CRM integration"
}
```

## Notes

Free / Basic / SMB editions have no CRM integration and cannot work — say this
early to avoid doomed evaluations. Live call states, server-side click-to-call
and recording-audio download need the optional `oduist/3cx-agent` sidecar on
the AI edition (8SC+), which is still validated against mocks only — do not
promise it in the post.
