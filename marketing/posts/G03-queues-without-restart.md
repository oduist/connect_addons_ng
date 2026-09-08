---
id: G3
title: Queues you reconfigure without a restart
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/callflows.md, docs/changelog.md]
---

## Post

Someone calls in sick. You need them out of the support queue — now, not tonight when it's safe to restart the PBX. ⏱️

With **Oduist Connect** on FreeSWITCH, that's a checkbox.

📋 Queues live under Connect ▸ FreeSWITCH ▸ FIFO Queues as ordinary Odoo records
👥 Members are PBX users and/or endpoint agents — add or remove them in the form
⏳ Max wait time, Music-on-Hold source, position announcements: same form
🚪 On timeout: hang up, send to voicemail, or transfer to a fallback extension
🔄 Changes take effect **on the next call**. No reload, no restart, no maintenance window

The queue is data, not a config file. Which means the supervisor can fix the rota, instead of filing a ticket for whoever has SSH.

What's the slowest change your phone system makes you wait for? 👇

#Odoo #FreeSWITCH #CallCenter #Telephony #VoIP

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · FS Queues",
  "headline": "Change the queue.",
  "headline_grad": "Don't restart the PBX.",
  "lede": "Agents, wait time, hold music and timeout routing are Odoo fields — and they *apply on the next call*.",
  "columns": ["Before", "Connect"],
  "rows": [
    {"f": "Edit a config file on the server", "m": ["✓", "—"]},
    {"f": "Reload or restart FreeSWITCH", "m": ["✓", "—"]},
    {"f": "Wait for a maintenance window", "m": ["✓", "—"]},
    {"f": "Change agents from an Odoo form", "m": ["—", "✓"]},
    {"f": "New settings live on the next call", "m": ["—", "✓"]}
  ],
  "footer": "Connect ▸ FreeSWITCH ▸ FIFO Queues"
}
```

## Notes

"Before" column describes hand-maintained FreeSWITCH config, not a named
competitor. Keep it that way in replies.
