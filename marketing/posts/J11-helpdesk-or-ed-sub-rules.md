---
id: J11
title: Why isn't it creating tickets
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_helpdesk/docs/configuration.md]
---

## Post

"Auto Create Tickets is ON. Why isn't it creating tickets?" 🎫

Nine times out of ten: the master toggle is on and **every sub-toggle underneath it is off**. The master switch enables the direction; the sub-rules decide which calls actually qualify.

And they're **OR-ed**, not AND-ed. The three incoming rules — answered / not answered / unknown callers — are evaluated in order, and a ticket is created if **any enabled rule matches**. So an answered call from an unknown number creates a ticket as soon as "For Answered Calls" is on, whether or not "For Unknown Callers" is.

Two more reasons for silence: auto-creation runs in `register_call()`, i.e. **after the call fully ends** (that's what makes answered-vs-missed reliable), and outgoing calls to your own PBX users never create a ticket.

Which "obviously on" setting has fooled you? 👇

#Odoo #Helpdesk #Telephony

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · Helpdesk",
  "headline": "Master on.",
  "headline_grad": "Sub-rules off.",
  "lede": "The three incoming sub-rules are *OR-ed* — any enabled rule that matches creates the ticket. All off means never.",
  "columns": ["Ticket"],
  "rows": [
    {"f": "Master toggle off", "m": ["—"]},
    {"f": "Master on, all three sub-toggles off", "m": ["—"]},
    {"f": "Answered call · \"For Answered Calls\" on", "m": ["✓"]},
    {"f": "Missed call · \"For Not Answered Calls\" on", "m": ["✓"]},
    {"f": "Unknown caller · \"For Unknown Callers\" on", "m": ["✓"]},
    {"f": "Outgoing call to a colleague on the PBX", "m": ["—"]}
  ],
  "footer": "Evaluated in register_call() — after the call ends, so answered vs missed is reliable"
}
```

## Notes

Requires Odoo Enterprise Helpdesk. The "call already has a ticket is skipped"
rule is another common reason nothing appears — good material for a reply.
