---
id: D03
title: Voice ordering — an AI agent that places real sale orders
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_elevenlabs_sale/docs/tools.md, connect_elevenlabs/docs/agents.md]
---

## Post

"That's S00001 — I've placed it under your account."

The caller heard that from an AI. The order was a real `sale.order` in Odoo, created mid-conversation. 🛒

How **Oduist Connect + ElevenLabs** does voice ordering:

📦 `get_products` reads your **published** product templates — name, public category, list price, sale description
🧾 `create_sale_order` writes one order line for the chosen variant at its list price, addressed to the caller's contact
🔢 The tool returns the new order reference, so the agent can read it back on the call
🔐 Every call is an HTTP POST into your Odoo, guarded by the agent token — 401 without it
✅ The order lands under Sales, linked to the caller, ready for a human to confirm

The AI takes the order. Your team still decides what ships.

Would you let a voice agent create the order, or only draft it for review? 👇

#Odoo #VoiceAI #Sales #Ecommerce

## Card

```json
{
  "template": "dialog",
  "accent": "purple",
  "kicker": "Oduist Connect · Voice Ordering",
  "headline": "The caller orders.",
  "headline_grad": "Odoo gets S00001.",
  "lede": "An AI agent reads your published catalogue and creates a *real sale order* while the caller is still on the phone.",
  "bubbles": [
    {"side": "left", "who": "Caller", "text": "\"Two of the 20-litre buckets, same account as last time.\""},
    {"side": "right", "who": "AI Agent", "text": "\"Done — that's order S00001, two units at the list price. Your sales rep will confirm it today.\""}
  ],
  "badge": "✓ sale.order S00001 created in Odoo",
  "footer": "create_sale_order · published products only · token-authenticated"
}
```

## Notes

Deliberately no stock claim: `get_products` returns a hard-coded
`items_in_stock: 10`, documented as a placeholder. Never say the agent checks
availability.

The order is a single line at list price — do not imply multi-line orders,
discounts or pricelists.
