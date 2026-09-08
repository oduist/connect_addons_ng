---
id: G5
title: Queue fallback routing
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [docs/changelog.md, connect/docs/user/callflows.md]
---

## Post

The worst outcome of a call queue isn't a long wait. It's a click. ☎️➡️🔇

Caller holds. Music plays. Nobody picks up. Timeout hits — and the line just dies. No message, no callback, no trace of a customer who tried.

**Oduist Connect** shipped queue fallback routing so that ending never happens by default. When a FreeSWITCH FS Queue times out, you choose what happens next:

📼 **Voicemail** — record the caller, so the team calls back with the message in hand
↪️ **Transfer** — hand the call to another extension: an overflow team, a manager, an after-hours flow
🔚 **Hang up** — still available, but now it's a decision you made, not a default you inherited

Set it on the queue's timeout settings, alongside max wait time and Music-on-Hold. The change applies on the next call.

A queue nobody answers should hand the call on, not drop it.

What does your queue do at minute three? 👇

#Odoo #FreeSWITCH #CallQueue #CustomerService #Telephony

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · FS Queues",
  "headline": "Timeout is not",
  "headline_grad": "a hang-up.",
  "lede": "When nobody answers, the queue hands the call on — *voicemail, transfer, or a deliberate hang-up*.",
  "nodes": [
    {"t": "Queue timeout", "s": "max wait reached", "c": "core"},
    {"t": "Fallback", "s": "voicemail · transfer · hangup", "c": "app"}
  ],
  "link_label": "hands off to",
  "footer": "Configured on the queue · applies on the next call"
}
```

## Notes

Shipped 2026-08 for `connect_freeswitch`. Timeout options (hangup / voicemail /
transfer) are listed in callflows.md.
