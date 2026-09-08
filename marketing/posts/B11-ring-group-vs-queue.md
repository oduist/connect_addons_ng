---
id: B11
title: Ring group vs call queue — which do you need
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/callflows.md]
---

## Post

Ring group or call queue? The answer is decided by one thing: what the caller hears while they wait. 🎧

**Ring group** — every user in the group rings at the same time, first to pick up takes the call. If nobody answers before the timeout, the call moves on: voicemail, another destination, or into a queue. It works on any provider, it is a call-flow setting, and there is nothing to operate.

**FS Queue** (FreeSWITCH) — the caller is answered, put on music on hold, and agent phones ring in the background. It adds what a ring group cannot do: max wait time, optional position announcements, endpoint agents alongside Odoo users, and a timeout action of hang up, voicemail or transfer. Changes to agents or wait time apply on the next call — no restart.

Rule of thumb: three people and a quiet line → ring group. A line that queues at 9 a.m. → queue.

Both can be an IVR choice, and a queue needs no extension of its own.

Which one is your sales line running? 👇

#Odoo #CallCenter #FreeSWITCH #VoIP #IVR

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · Call flows",
  "headline": "Ring them all,",
  "headline_grad": "or make them wait.",
  "lede": "A ring group rings everyone at once. A queue answers first, holds the caller on music, *and rings agents in the background*.",
  "columns": ["Ring group", "FS Queue"],
  "rows": [
    {"f": "Rings every member at once", "m": ["✓", "—"]},
    {"f": "Works on any provider", "m": ["✓", "—"]},
    {"f": "Music on hold while waiting", "m": ["—", "✓"]},
    {"f": "Announce caller position", "m": ["—", "✓"]},
    {"f": "Max wait time", "m": ["—", "✓"]},
    {"f": "Endpoint agents, not just users", "m": ["—", "✓"]},
    {"f": "Voicemail on timeout", "m": ["✓", "✓"]}
  ],
  "footer": "Both usable as an IVR choice · a queue needs no extension"
}
```

## Notes

FS Queues are `connect_freeswitch`-only. The docs describe queue agents as
"ringing in the background" without stating simultaneous vs sequential — the
card's first row claims simultaneous ring only for the ring group, which is
what the docs say. Do not extend that claim to queues in the comments.
