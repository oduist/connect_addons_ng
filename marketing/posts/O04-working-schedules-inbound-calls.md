---
id: O04
title: Working schedules for inbound calls
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch_website/docs/admin/working-schedule.md, docs/changelog.md]
---

## Post

Nothing says "closed for the holidays" quite like forty rings and no answer. 🔔

Working schedules in **Oduist Connect** decide what an inbound number does before it rings anyone. Three layers, checked in order:

📅 **Working schedule** — the weekly hours of a standard Odoo working calendar, in its own timezone
🎄 **Public holidays** — taken from that calendar's global time off, with an optional spoken message for callers
✨ **Special working days** — irregular hours for specific dates. They always win, and they can *open* a day that's normally closed, like a Saturday
🔀 On each number, **After-hours Routing** sends the call to another user, call flow or queue instead of dropping it
🌐 Add the website module and your site shows a 🟢/🔴 phone indicator and the next days' opening hours, localised for the visitor

Schedules are reusable — any number of DIDs can point at one — and a 14-day preview plus an availability calendar show you exactly what callers will get.

How does your business handle the call that arrives at 19:05? 👇

#Odoo #Telephony #CustomerService #FreeSWITCH

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · Schedules",
  "headline": "Your number knows",
  "headline_grad": "when you're closed.",
  "lede": "Weekly hours, public holidays and special days on one *reusable schedule* — with a route for the calls that arrive outside them.",
  "columns": ["Plain DID", "With a schedule"],
  "rows": [
    {"f": "Rings the team in hours", "m": ["✓", "✓"]},
    {"f": "After-hours route", "m": ["—", "✓"]},
    {"f": "Spoken holiday message", "m": ["—", "✓"]},
    {"f": "Special / extra open days", "m": ["—", "✓"]},
    {"f": "Opening hours on your website", "m": ["—", "✓"]},
    {"f": "14-day preview & availability", "m": ["—", "✓"]}
  ],
  "footer": "Built on Odoo working calendars · reusable across numbers"
}
```

## Notes

Time-sensitive: shipped in the 2026-07 changelog. Evergreen as written — the
post does not claim novelty, so it can be published at any time.

Scope check for replies: schedules apply to FreeSWITCH numbers, and the website
snippets require `connect_freeswitch_website` (which needs Odoo `website`).
