---
id: G13
title: Phone status on your website
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch_website/docs/admin/working-schedule.md]
---

## Post

Your website says "Mon–Fri 9–5". Your phone system knows you close at 13:00 today. Guess which one the visitor believes. 🕐

Two building blocks in the Odoo website editor fix that, driven by the *same* working schedule that routes your calls:

🟢 **Phone Status** — for footers: the number with a live green/red indicator and an optional "(available until 16:00)" or "(opens tomorrow 08:00)". Options for a `tel:` link and a page to link from the indicator
📅 **Phone Opening Hours** — for contact pages: effective hours for the next N days, with holiday and special-day labels. Long or short date format, your call
🌍 Dates and times localized in the *visitor's* language
🔒 Only numbers with **Use Working Schedule** enabled can be selected, and the public JSON endpoints behind the widgets expose nothing else

One source of truth. Edit the schedule, and the routing, the footer and the contact page all change together — because they were never separate.

How out of date are the opening hours on your site right now? 👇

#Odoo #Website #Telephony #FreeSWITCH #CustomerExperience

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Website",
  "headline": "One schedule.",
  "headline_grad": "Phone and website.",
  "lede": "The working schedule that routes your calls also *drives the widgets on your site* — footer status and opening hours.",
  "nodes": [
    {"t": "Working Schedule", "s": "hours · holidays · special days", "c": "cyan"},
    {"t": "Inbound routing", "s": "open vs after-hours destination", "c": "provider"},
    {"t": "Website snippets", "s": "Phone Status · Opening Hours", "c": "app"}
  ],
  "link_label": "drives",
  "footer": "connect_freeswitch_website · localized for the visitor"
}
```

## Notes

Requires the Odoo `website` module and `connect_freeswitch_website` (not
auto-installed). Endpoints: `/freeswitch/schedule/status/<id>` and
`/freeswitch/schedule/opening_hours/<id>`.
