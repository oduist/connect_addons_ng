---
id: F13
title: Employee call history without manual tagging
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_hr/docs/configuration.md, connect_hr/docs/index.md]
---

## Post

Ask HR to tag calls by hand and you'll get a complete record for about two weeks. 🏷️

**Oduist Connect HR** does it from the number. When a call is created, the module takes the *other* party — the caller on an incoming call, the number dialled on an outgoing one — normalises it, and looks it up against the employee's **Work Phone** and **Work Mobile**. Those two fields only.

📇 One match → the employee is attached to the call, and appears on the **Calls** smart button on their form
🧯 Numbers shorter than the extension threshold are skipped, so internal extensions never match a full phone number
🔒 A call that already has an employee is left alone — manual assignments survive
🐞 Every match is written to the Connect debug log, so "why did it link that?" is answerable
🤖 With AI summaries on, the summary is posted to the employee's chatter

No create button, by design: employees come from onboarding, not from a ring.

Field teams and their work mobiles — how are those calls tracked today? 👇

#Odoo #HR #Telephony #Automation #ERP

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · HR",
  "headline": "The number is",
  "headline_grad": "the only tag you need.",
  "lede": "Calls are matched against the employee's *Work Phone* and *Work Mobile* — normalised, indexed, and never overwriting a manual link.",
  "nodes": [
    {"t": "Call", "s": "caller or called number", "c": "cyan"},
    {"t": "Employee", "s": "work phone · work mobile", "c": "app"}
  ],
  "link_label": "normalised match",
  "footer": "Lookup only — employees are never created from a call"
}
```

## Notes

Matching is limited to `work_phone` and `mobile_phone`; private phone fields are
not used. Worth stating if privacy questions come up in comments.
