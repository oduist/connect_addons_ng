---
id: D04
title: Self-service order status by phone
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_elevenlabs_sale/docs/tools.md]
---

## Post

"Our customers won't talk to a robot." Maybe. But they also won't wait on hold to hear a delivery date. 📦

"Where is my order?" is the single most repeatable call in any sales team's day — and an **Oduist Connect** voice agent handles it end to end:

📋 `get_sale_orders` reads back the caller's own order references
🔎 `get_sale_order_info` opens one order: its lines with quantities, the commitment/delivery date, the shipping weight
🙋 It names the salesperson who owns the order — and their internal extension
🔀 So the next sentence can be "shall I put you through to them?" instead of "someone will call you back"
🔒 Every lookup is scoped to the caller's own partner record. No fishing for other people's orders.

The routine call gets answered instantly. Your reps keep the calls that actually need a rep.

How many "where is my order?" calls does your team take in a week? 👇

#Odoo #VoiceAI #Sales #CustomerService

## Card

```json
{
  "template": "dialog",
  "accent": "purple",
  "kicker": "Oduist Connect · Order Status",
  "headline": "\"Where is my order?\"",
  "headline_grad": "Answered without a rep.",
  "lede": "The agent reads the caller's *own* orders — lines, delivery date, salesperson — and can transfer to that rep.",
  "bubbles": [
    {"side": "left", "who": "Caller", "text": "\"Hi — any news on S00042?\""},
    {"side": "right", "who": "AI Agent", "text": "\"S00042 has 2 × pump unit, delivery committed for the 14th. Your rep is Marta on extension 204 — shall I put you through?\""}
  ],
  "badge": "✓ scoped to the caller's own partner",
  "footer": "get_sale_orders · get_sale_order_info · read-only lookups"
}
```

## Notes

`get_sale_order_info` requires both `partner_id` and `order_name`, so the agent
must have identified the caller first. The salesperson extension comes from
`user.connect_user.twilio_exten.number` and can read back as "No extension".
