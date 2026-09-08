---
id: J16
title: Bird authenticates fine but returns 403
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_bird/docs/admin/bird-setup.md]
---

## Post

"The Bird key authenticates fine — but half the endpoints answer **403**." 🪶

That's not a broken key. That's a key without scopes.

A Bird access key (`bk_...`) authenticates as soon as it exists. Authorization is per product, and **a key missing a scope authenticates but receives 403 on that product's endpoints**. So SMS sends, WhatsApp 403s. Or everything works until **SETUP WEBHOOKS** returns 403 because the webhooks scope was never granted.

Create the key with the full list — **sms, whatsapp, voice, numbers, webhooks** — in User Settings → Security → Access Keys, and copy it immediately: the full key is shown **only once, at creation**.

Locked out of webhooks? Register the endpoint by hand in the Bird dashboard and paste the `whsec_` secret into **Webhook Signing Key**.

Which API's 403 message has annoyed you most? 👇

#Odoo #Bird #API

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Bird",
  "headline": "Authenticated.",
  "headline_grad": "Not authorized.",
  "lede": "A `bk_...` key without a product scope still logs in — it just answers *403* on that product. Create the key with all five.",
  "tiles": [
    {"sym": "sms", "nm": "Text messaging", "c": "provider"},
    {"sym": "wa", "nm": "WhatsApp", "c": "app"},
    {"sym": "voice", "nm": "Call ledger", "c": "cyan"},
    {"sym": "num", "nm": "Number import", "c": "provider"},
    {"sym": "hook", "nm": "Webhook setup", "c": "magenta"},
    {"sym": "403", "nm": "Any missing scope", "c": "core", "hero": true}
  ],
  "footer": "The full access key is shown only once, at creation — copy it then"
}
```

## Notes

Also worth flagging in replies: as of mid-2026 Bird delivers webhook events for
the email product only, so outgoing SMS statuses are polled every 5 minutes and
inbound messages cannot be received yet.
