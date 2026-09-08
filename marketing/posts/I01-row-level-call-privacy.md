---
id: I01
title: Row-level call privacy
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/admin/security.md, specs/connect_core.md]
---

## Post

"Can our sales rep open the call list and hear a colleague's conversation?" — the first question every IT team asks about telephony in the ERP. 🔒

In **Oduist Connect** the answer is enforced by Odoo record rules, not by a hidden menu:

👤 A Connect User sees calls, messages and recordings tied to their own PBX user — or where they are the caller, the answering user or the sender
🙈 Everyone else's calls simply don't exist in their list, search or count
🪪 Users see only their own PBX user record; the rest stay invisible
🛠️ Connect Admin (`connect.group_admin`) sees everything and owns the configuration
🚪 The same rules answer a direct URL or a bookmark — there is no back door around them

Row-level, evaluated by the database on every read. No "please don't look" policy document.

Who in your company should be able to replay a recording — the rep, the manager, or nobody? 👇

#Odoo #Telephony #Security #ERP

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · Security",
  "headline": "Reps see their calls.",
  "headline_grad": "Only their calls.",
  "lede": "Row-level privacy enforced by *Odoo record rules* — not by hiding a menu.",
  "columns": ["Connect User", "Connect Admin"],
  "rows": [
    {"f": "Own calls, messages, recordings", "m": ["✓", "✓"]},
    {"f": "Colleagues' call history", "m": ["—", "✓"]},
    {"f": "Own PBX user record", "m": ["✓", "✓"]},
    {"f": "All PBX users", "m": ["—", "✓"]},
    {"f": "Edit numbers & call flows", "m": ["—", "✓"]},
    {"f": "Connect settings", "m": ["—", "✓"]}
  ],
  "footer": "connect.group_user · connect.group_admin · connect.group_webhook"
}
```

## Notes

Record-rule scope wording comes from `specs/connect_core.md` (own `connect.user`
plus `caller_user` / `answered_user` / `sender_user`). Keep that phrasing if a
reader asks for detail.
