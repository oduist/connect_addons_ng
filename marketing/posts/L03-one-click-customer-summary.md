---
id: L03
title: One-click customer summary
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_memory/docs/user/memory.md, specs/connect_memory.md]
---

## Post

Forty emails, six orders, two disputes — and ninety seconds before the customer picks up. Scrolling the chatter is not a strategy. ⏱️

On any contact in Odoo, **Oduist Connect Memory** adds a **Customer summary** button:

🖱️ One click asks the memory engine for a concise summary of everything it has remembered about that customer
📥 The answer arrives asynchronously as an entry in Connect ▸ Memory ▸ Inbox, with readable text — the request never blocks your form
🔘 Next to it, a **Memory events** smart button shows the count and every captured item with the record it came from
🙈 Only real correspondence with external contacts is in there — internal notes between colleagues and system messages are ignored
🧑‍💼 Connect Users can ask; the backfill jobs and wizard stay admin-only

Not a chatbot bolted onto a contact form. A durable memory you can query, built from your own records.

What's the one question you'd ask about a customer before every call? 👇

#Odoo #AI #CRM #Sales #CustomerMemory

## Card

```json
{
  "template": "dialog",
  "accent": "purple",
  "kicker": "Oduist Connect · Memory",
  "headline": "Ninety seconds",
  "headline_grad": "before the call.",
  "lede": "One button on the contact form asks the memory engine — the answer lands in your *Memory Inbox*.",
  "bubbles": [
    {"side": "left", "who": "You · contact form", "text": "\"Customer summary\""},
    {"side": "right", "who": "Customer memory", "text": "\"Eight orders since March, two edited after confirmation, pays about five days late. Last exchange: a delivery-date complaint on the open order.\""}
  ],
  "badge": "✓ Answer appears in Connect ▸ Memory ▸ Inbox",
  "footer": "Asynchronous by design — the request never blocks the form"
}
```

## Notes

The bubble text is an illustrative mock built from documented event types
(orders, renegotiation edits, payment lateness, correspondence). Not real data.
