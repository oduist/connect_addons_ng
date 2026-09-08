---
id: N08
title: Idempotent webhooks, designed for replay
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch/docs/admin/parking.md, connect_elevenlabs/docs/webhooks-security.md]
---

## Post

Every webhook you receive will eventually arrive twice. Plan for it, or debug it at 2 a.m. 🔁

A few of the rules we hold ourselves to in Oduist Connect:

🅿️ **Parking events are idempotent by construction.** `entered` and `released` describe a state, not a transition, so a replay is a no-op — no "slot already occupied" ghosts
🆔 **Dedupe on the provider's own id.** The ElevenLabs post-call webhook dedupes by `conversation_id`, so re-delivery costs nothing
⏰ **Reject stale replays explicitly.** Post-call deliveries carry a signed timestamp; anything older than 30 minutes is rejected, HMAC valid or not
✅ **Return 200 on internal errors — deliberately.** If our processing throws, we still answer 200 so the platform doesn't retry a payload that will fail identically. The error belongs in our log, not in a retry storm
🛟 **Never let a bug drop a live call.** The conversation-initiation controller always returns a valid JSON envelope; an internal failure becomes empty variables, not a dead conversation

A webhook you can safely replay is a webhook you can debug by replaying it.

Where would you draw the 200-vs-500 line? Tell me why this is wrong. 👇

#Odoo #Webhooks #API #DistributedSystems #Idempotency

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Webhooks",
  "headline": "It will arrive twice.",
  "headline_grad": "Design for that.",
  "lede": "State-shaped events, dedupe by provider id, reject stale signatures. *And answer 200 on our own bugs* so retries don't storm.",
  "tiles": [
    {"sym": "id", "nm": "dedupe key", "c": "cyan", "hero": true},
    {"sym": "30m", "nm": "replay window", "c": "cyan"},
    {"sym": "200", "nm": "on our error", "c": "core"},
    {"sym": "{}", "nm": "always valid JSON", "c": "app"},
    {"sym": "P", "nm": "parking no-op", "c": "provider"},
    {"sym": "sig", "nm": "HMAC verified", "c": "magenta"}
  ],
  "footer": "Signature failures still return 401 — 200 is for our bugs, not for bad callers"
}
```

## Notes

The 30-minute tolerance and the 200-on-error behaviour are ElevenLabs-specific
(post-call webhook). Parking idempotency is FreeSWITCH. Don't present them as one
shared framework.
