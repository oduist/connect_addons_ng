---
id: C07
title: How to connect Bird (MessageBird) to Odoo
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_bird/docs/admin/bird-setup.md]
---

## Post

Bird ships no browser calling SDK. So **Oduist Connect** ships no Bird web phone — and says so on the setup page rather than in a support ticket three weeks in. 🐦

What you get instead is a two-leg callback: Bird rings the agent's own phone first, then bridges the customer. Any mobile or landline works.

Setting it up:

🔑 One `bk_...` access key with the sms, whatsapp, voice, numbers and webhooks scopes — a key missing one just returns 403 on that product
🔄 **SYNC BIRD ACCOUNT** imports your numbers and approved WhatsApp templates
🪝 **SETUP WEBHOOKS** registers a single signed endpoint (Standard Webhooks); the signing secret is issued exactly once
⏺️ Recordings are downloaded by a scheduled job and transcribed like any other provider
⚠️ Platform caveat, stated up front: as of mid-2026 Bird delivers webhook events for its email product only, so outgoing delivery statuses are polled every 5 minutes and inbound messages can't be received yet

We'd rather you evaluate on facts than discover them.

Would that caveat rule Bird out for you, or is messaging enough? 👇

#Bird #MessageBird #Odoo #WhatsApp #SMS

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Bird",
  "headline": "Bird in Odoo.",
  "headline_grad": "Messaging first.",
  "lede": "SMS, WhatsApp templates and a call ledger — plus click-to-call as a *two-leg callback*, because Bird has no WebRTC SDK.",
  "tiles": [
    {"sym": "SMS", "nm": "Send & log", "c": "provider"},
    {"sym": "WA", "nm": "Templates", "c": "app"},
    {"sym": "NUM", "nm": "Numbers", "c": "cyan"},
    {"sym": "LOG", "nm": "Call ledger", "c": "core"},
    {"sym": "C2C", "nm": "Callback dial", "c": "magenta"},
    {"sym": "REC", "nm": "Recordings", "c": "memory"}
  ],
  "footer": "Standard-Webhooks signature · scoped access key · OpenAI transcripts"
}
```

## Notes

The mid-2026 webhook limitation is the whole risk of this post: re-verify it
against the Bird platform before publishing, and drop or soften the bullet if
`sms.*` / `voice.*` events have shipped since.
