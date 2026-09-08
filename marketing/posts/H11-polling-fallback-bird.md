---
id: H11
title: When your provider has no inbound webhooks
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_bird/docs/admin/bird-setup.md]
---

## Post

Here's something you won't find on a feature page: our Bird integration cannot receive inbound messages. 🙃

Not because we didn't build it. As of mid-2026 the Bird platform delivers webhook events for the **email product only** — `sms.*`, `whatsapp.*` and `voice.*` events can't be subscribed to yet.

So we shipped the honest fallback:

⏱️ A scheduled action polls outgoing message delivery statuses every 5 minutes
🎙️ A second one downloads finished call recordings every 2 minutes (Bird's download links are short-lived, so audio is stored as an Odoo attachment)
📤 Outbound SMS, WhatsApp templates, click-to-call and the call ledger all work today
📥 Inbound messages do not — and we say so in the admin guide, in a warning box, before you buy
🔌 The `/bird/webhook` endpoint is already registered and signature-verified, so the day Bird ships those events it's a switch, not a project

If two-way messaging is the requirement, pick Twilio, Telnyx or Infobip. That's the useful answer, even when it costs us a sale.

Would you rather see a limitation in the docs, or discover it in week three? 👇

#Odoo #Bird #MessageBird #SMS #EngineeringHonesty

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Bird",
  "headline": "No inbound webhooks?",
  "headline_grad": "We say so out loud.",
  "lede": "Bird delivers webhook events for email only today, so Connect *polls* delivery statuses every 5 minutes — and the admin guide warns you before you buy.",
  "nodes": [
    {"t": "Bird platform", "s": "sms/whatsapp/voice events not subscribable", "c": "provider"},
    {"t": "Odoo", "s": "status poll · recording fetch", "c": "app"}
  ],
  "link_label": "Poll every 5 min",
  "footer": "Outbound works · inbound messages do not · /bird/webhook ready for the day it lands"
}
```

## Notes

The mid-2026 statement is dated on purpose — re-verify against
`connect_bird/docs/admin/bird-setup.md` before publishing in case Bird has since
shipped the events.
