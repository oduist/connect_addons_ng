---
id: G15
title: The Availability calendar
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/calls.md, connect_freeswitch_website/docs/admin/working-schedule.md]
---

## Post

Weekly hours, plus public holidays, plus a special Saturday, plus a half-day nobody remembers. Now answer this: **is the support line open next Thursday at 16:30?** 🤔

Nobody should have to compute that in their head.

**Connect → Availability** in **Oduist Connect** shows the answer as a calendar:

🟩 Computed **Available** windows — the actual result of all your rules
⬜ All-day **Closed** markers, so a shut day is visible at a glance
🧱 The raw layers underneath — Working Schedule, Public Holiday, Special Working Day — toggled with search filters when you need to know *why*
🔍 Filter down to one schedule, or look at every schedule side by side
🔄 Slots regenerate automatically: nightly by cron and on every schedule, holiday or special-day change, over a rolling 60-day horizon

It's the same materialized schedule your inbound routing uses. So what you see in the calendar is what the caller gets — not a second, decorative copy of your hours.

Do you actually know when your phone lines are open next month? 👇

#Odoo #Telephony #BusinessHours #FreeSWITCH #Operations

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Availability",
  "headline": "Your phone hours,",
  "headline_grad": "as a calendar.",
  "lede": "Computed *Available* windows and *Closed* days — with the underlying layers one filter away.",
  "tiles": [
    {"sym": "🟩", "nm": "Available window", "c": "app", "hero": true},
    {"sym": "⬜", "nm": "Closed all day", "c": "core"},
    {"sym": "📅", "nm": "Working schedule", "c": "cyan"},
    {"sym": "🎄", "nm": "Public holiday", "c": "memory"},
    {"sym": "⭐", "nm": "Special day", "c": "magenta"},
    {"sym": "60d", "nm": "Rolling horizon", "c": "provider"}
  ],
  "footer": "Same materialized schedule that routes inbound calls"
}
```

## Notes

Horizon is controlled by the `connect.schedule_slot_horizon_days` system
parameter (default 60 days).
