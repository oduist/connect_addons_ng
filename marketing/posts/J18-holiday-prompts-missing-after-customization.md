---
id: J18
title: Holiday prompts missing after a dialplan customization
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch_website/docs/admin/working-schedule.md]
---

## Post

The public holiday is configured. The prompt message is typed in. Callers on Christmas Day hear… nothing, then a hangup. 🎄

Check whether someone customized the `dialplan_inbound_did` XML template.

Odoo generates the FreeSWITCH dialplan from Jinja2 templates, and a customized template is frozen at the version it was copied from — it keeps working, it just never receives new blocks. The holiday prompt is rendered by a `schedule_prompt` block that a pre-customization copy simply doesn't contain.

Two ways out: **Reset to Default** in the template form header, or merge the `schedule_prompt` block into your version if the customization is load-bearing. Templates carrying changes are flagged **Customized** in the list view.

And with no after-hours destination configured, callers outside working hours hear the prompt and the call is hung up — that part is by design.

Ever been bitten by a customized template missing an upstream block? 👇

#Odoo #FreeSWITCH #IVR

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Schedules",
  "headline": "The prompt is set.",
  "headline_grad": "The template is old.",
  "lede": "A customized `dialplan_inbound_did` never gains the *schedule_prompt* block — so holiday messages are silently skipped.",
  "nodes": [
    {"t": "dialplan_inbound_did", "s": "customized copy, frozen in time", "c": "core"},
    {"t": "schedule_prompt block", "s": "renders the holiday message", "c": "app"}
  ],
  "link_label": "missing",
  "footer": "Reset to Default in the template header — or merge the block by hand"
}
```

## Notes

Working schedules need `connect` ≥ 19.0.4.1.0 and `connect_freeswitch` ≥
19.0.2.1.0; the website widgets are a separate module (`connect_freeswitch_website`).
