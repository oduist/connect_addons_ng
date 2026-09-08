---
id: H07
title: Delivery statuses that tell you the truth
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/messages.md, connect_twilio/docs/messaging.md, connect_infobip/docs/admin/infobip-setup.md]
---

## Post

"Sent" is the most misleading word in business messaging. It means the carrier took your message — not that a human ever saw it. 📤

Oduist Connect keeps eight distinct message statuses so you can tell those apart:

📝 **Draft** → **Queued** → **Sending** — still on your side
📮 **Sent** — handed to the carrier
📬 **Delivered** — it reached the recipient's device
👁️ **Read** — the recipient actually opened it (WhatsApp only)
❌ **Failed** — it couldn't be sent
🚧 **Undeliverable** — the carrier couldn't deliver it

Statuses update on their own: delivery callbacks from your provider write straight back onto the message record. When one fails, a **Retry** button on the record resends it — no copy-paste into a portal.

The practical payoff: "customer never got the reminder" stops being a theory and becomes a filter on a list view.

Which status would change how your team follows up — Delivered, or Read? 👇

#Odoo #SMS #WhatsApp #CustomerCommunication #Automation

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Message Status",
  "headline": "Sent isn't delivered.",
  "headline_grad": "Delivered isn't read.",
  "lede": "Eight statuses on every SMS and WhatsApp message, *updated by provider callbacks* — plus a Retry button when one fails.",
  "tiles": [
    {"sym": "①", "nm": "Draft", "c": "provider"},
    {"sym": "②", "nm": "Queued", "c": "provider"},
    {"sym": "③", "nm": "Sending", "c": "provider"},
    {"sym": "④", "nm": "Sent", "c": "cyan"},
    {"sym": "⑤", "nm": "Delivered", "c": "app"},
    {"sym": "👁", "nm": "Read · WhatsApp", "c": "magenta", "hero": true},
    {"sym": "✕", "nm": "Failed", "c": "core"},
    {"sym": "⚠", "nm": "Undeliverable", "c": "core"},
    {"sym": "↻", "nm": "Retry", "c": "memory"}
  ],
  "footer": "Read status is WhatsApp-only · statuses arrive on the provider webhook"
}
```

## Notes

Read is explicitly WhatsApp-only in the docs — keep the qualifier in both the
post and the card tile.
