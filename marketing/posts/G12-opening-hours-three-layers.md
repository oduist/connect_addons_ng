---
id: G12
title: Opening hours, three layers deep
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch_website/docs/admin/working-schedule.md]
---

## Post

Christmas Eve. You close at 13:00 instead of 17:00. Your phone system has one weekly schedule and no opinion about December 24th. 🎄

**Oduist Connect** resolves opening hours in three layers, checked in this order for every inbound call:

1️⃣ **Special Working Days** — irregular hours for a specific date. They always win, and they can *extend* as well as shorten: opening a Saturday is just a special day
2️⃣ **Public Holidays** — closures taken from the working calendar's global time off, with an optional voice message for callers
3️⃣ **Working Schedule** — the weekly hours of a standard Odoo `resource.calendar`, timezone included

The order is what makes it usable. A single date beats a holiday; a holiday beats the weekly grid. To fully close a date, use a holiday — special days only ever describe *working* windows.

Schedules are reusable: any number of DIDs can point at the same one, and a 14-day preview shows the computed result before a caller finds out.

Which exception broke your phone hours last year? 👇

#Odoo #Telephony #FreeSWITCH #BusinessHours #VoIP

## Card

```json
{
  "template": "dialog",
  "kicker": "Oduist Connect · Working Schedules",
  "headline": "Special days beat",
  "headline_grad": "holidays beat hours.",
  "lede": "Three layers, checked in order on every inbound call — *a single date always wins* over the weekly grid.",
  "bubbles": [
    {"side": "left", "who": "Caller · Dec 24, 15:40", "text": "(dials the main line — the weekly calendar says open until 17:00)"},
    {"side": "right", "who": "Schedule", "text": "Special Working Day for Dec 24 = 08:00–13:00. Closed. The call takes the after-hours route instead."}
  ],
  "badge": "✓ 14-day preview on the schedule form",
  "footer": "Built on Odoo resource.calendar · reusable across numbers"
}
```

## Notes

Requires `connect` ≥ 19.0.4.1.0 and `connect_freeswitch` ≥ 19.0.2.1.0. Schedule
math runs in the calendar's timezone.
