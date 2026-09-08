---
id: G4
title: Four ways to route a caller into a queue
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/callflows.md]
---

## Post

Four. There are exactly four ways a caller ends up in a queue — and three of them need no extension number at all. 🎯

In **Oduist Connect** (FreeSWITCH FS Queues):

1️⃣ **Direct dial** — give the queue an extension and dial it. Optional, and only for this case
2️⃣ **IVR choice** — "Press 2 for Support" points straight at the queue
3️⃣ **IVR no-choice default** — the caller says nothing, the timeout fires, and they land in the queue instead of nowhere
4️⃣ **Ring-group fallback** — nobody in the group picks up, so the call moves into the queue *before* voicemail

Then the caller experience is the same every time: a short "please hold", Music-on-Hold while agent phones ring in the background, connected to the first agent who answers.

Most systems make you invent an extension for every hop. Here the queue is just a destination.

Which of the four is your busiest path? 👇

#Odoo #FreeSWITCH #CallQueue #ContactCenter #Telephony

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · FS Queues",
  "headline": "Four doors into",
  "headline_grad": "the same queue.",
  "lede": "Direct dial, IVR choice, IVR timeout or ring-group fallback — *only the first one needs an extension*.",
  "tiles": [
    {"sym": "1", "nm": "Direct dial", "c": "provider"},
    {"sym": "2", "nm": "IVR choice", "c": "cyan"},
    {"sym": "3", "nm": "No-choice default", "c": "cyan"},
    {"sym": "4", "nm": "Ring-group fallback", "c": "app", "hero": true},
    {"sym": "MoH", "nm": "Music on hold", "c": "memory"},
    {"sym": "1st", "nm": "Agent to answer", "c": "magenta"}
  ],
  "footer": "Music-on-hold · position announce · timeout routing"
}
```

## Notes

FS Queues require `connect_freeswitch`. The queue's own extension is optional
and only needed for direct dialing (callflows.md).
