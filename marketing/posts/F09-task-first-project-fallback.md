---
id: F09
title: Task-first, project-fallback linking
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_project/docs/configuration.md, connect_project/docs/index.md]
---

## Post

A call from a client on a running project should land on the *task* someone is working on — not on the project folder, where it quietly rots. 📁

So **Oduist Connect Project** links in a fixed order:

1️⃣ Already linked by hand? Nothing happens — a manual assignment is never overwritten
2️⃣ Otherwise, the caller's most recent **open task** — open meaning a kanban stage that isn't folded, so Done and Cancelled stages don't count
3️⃣ No open task? The caller's most recent **project** instead
🎯 Never both: a call carries a task *or* a project

It's the only Connect bridge with two target models, and that ordering is the whole design. Task-level context beats project-level context every time — the fallback exists so a call is never left homeless when the work hasn't been broken down yet.

Where would you want a client's call to land: task or project? 👇

#Odoo #ProjectManagement #Telephony #ERP #Automation

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · Project",
  "headline": "Task first.",
  "headline_grad": "Project as fallback.",
  "lede": "A call links to a task *or* a project — never both. An open task always wins.",
  "columns": ["Task", "Project"],
  "rows": [
    {"f": "Partner has an open task", "m": ["✓", "—"]},
    {"f": "All tasks in folded stages", "m": ["—", "✓"]},
    {"f": "No project either", "m": ["—", "—"]},
    {"f": "Call already linked by hand", "m": ["—", "—"]},
    {"f": "Calls smart button", "m": ["✓", "✓"]},
    {"f": "Recorded Calls tab", "m": ["✓", "✓"]}
  ],
  "footer": "Matched by the call's partner · most recent match wins"
}
```

## Notes

"Open task" is defined by an unfolded kanban stage, not by a fixed state field —
keep that wording if reviewers ask about Done/Cancelled.
