---
id: D01
title: What an Odoo phone number can do once an AI agent answers it
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_elevenlabs/docs/agents.md, connect_elevenlabs_helpdesk/docs/tools.md, connect_elevenlabs_sale/docs/tools.md]
---

## Post

Sixteen tools. That's how many actions an Oduist Connect voice agent can perform inside Odoo while the caller is still on the line. ☎️

Not "log the call" — actually change your database:

🎫 Helpdesk — create a ticket, search the caller's tickets, update priority or stage, post a note
🛒 Sales — read the published catalogue, place a sale order, look up an order's lines, delivery date and salesperson
📅 Calendar — offer free slots, book the meeting, list or cancel it
👤 Contacts — create a res.partner for an unknown caller and link it to the call
🔀 Transfer — hand the live call to a published extension

Every tool is an HTTP route back into your own Odoo, authenticated by a shared agent token. Nothing runs on someone else's copy of your data.

Which of these would you let an AI do unsupervised — and which one gets a human in the loop? 👇

#Odoo #VoiceAI #AIAgents #CustomerService

## Card

```json
{
  "template": "thesis",
  "accent": "purple",
  "kicker": "Oduist Connect · AI Agents",
  "headline": "Your phone number,",
  "headline_grad": "wired into Odoo.",
  "lede": "One inbound call, *sixteen tools* — tickets, orders, meetings and contacts, written straight into your database.",
  "tiles": [
    {"sym": "Tk", "nm": "Create ticket", "c": "purple", "hero": true},
    {"sym": "So", "nm": "Sale order", "c": "app"},
    {"sym": "Ct", "nm": "Catalogue", "c": "app"},
    {"sym": "Cal", "nm": "Free slots", "c": "cyan"},
    {"sym": "Bk", "nm": "Book meeting", "c": "cyan"},
    {"sym": "Pa", "nm": "New contact", "c": "magenta"},
    {"sym": "Up", "nm": "Update ticket", "c": "purple"},
    {"sym": "Ord", "nm": "Order status", "c": "app"},
    {"sym": "Tr", "nm": "Transfer", "c": "provider"}
  ],
  "footer": "ElevenLabs agents · webhook tools into your own Odoo"
}
```

## Notes

Tool count = 7 base webhook tools (transfer, create_partner, 5 calendar) + 5
helpdesk + 4 sale. Helpdesk tools need Odoo Enterprise Helpdesk; the sale tools
need Sales + eCommerce with published products. Say so if anyone asks in
comments.

Do not add stock availability to this list — `get_products` returns a
hard-coded `items_in_stock: 10`, not a real check.
