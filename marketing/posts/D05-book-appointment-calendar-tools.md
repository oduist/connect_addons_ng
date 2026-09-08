---
id: D05
title: Book an appointment by phone — five calendar tools
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_elevenlabs/docs/agents.md, connect_elevenlabs/docs/webhooks-security.md]
---

## Post

Five tools. That's the whole appointment-booking stack in **Oduist Connect** — and they all write to the Odoo calendar you already use. 📅

What the agent gets:

🕗 `calendar_get_available_slots` — free business-hours slots (08:00–18:00) for a given user on a given date
📆 `calendar_get_current_date` — the server's date and time, so "next Tuesday" resolves correctly
✅ `calendar_create_event` — books the meeting, de-duplicated by user + start/stop so a repeated turn can't double-book
📋 `calendar_get_meetings` — reads back what the caller already has
❌ `calendar_remove_meeting` — cancels one by id

The module ships an **Appointment Assistant** prompt template already wired to these tools, so a working booking agent is configuration, not development.

No second calendar to sync. No booking widget with its own database. The meeting appears in Odoo because it *was* created in Odoo.

What would you have it book first — service visits, demos, or consultations? 👇

#Odoo #VoiceAI #Scheduling #AIAgents

## Card

```json
{
  "template": "thesis",
  "accent": "purple",
  "kicker": "Oduist Connect · Calendar",
  "headline": "Booked by phone,",
  "headline_grad": "straight into Odoo.",
  "lede": "Five calendar tools and a ready *Appointment Assistant* template — the agent offers slots, books, reads back and cancels.",
  "tiles": [
    {"sym": "Slt", "nm": "Free slots", "c": "purple", "hero": true},
    {"sym": "Now", "nm": "Current date", "c": "cyan"},
    {"sym": "New", "nm": "Book event", "c": "app"},
    {"sym": "Lst", "nm": "My meetings", "c": "cyan"},
    {"sym": "Del", "nm": "Cancel", "c": "core"},
    {"sym": "Tpl", "nm": "Prompt template", "c": "magenta"}
  ],
  "footer": "08:00–18:00 business hours · de-duplicated bookings · Odoo calendar"
}
```

## Notes

The 08:00–18:00 window is what the controller implements today — do not present
it as configurable working hours.
