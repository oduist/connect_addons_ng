---
id: H12
title: MMS media that plays inline in Odoo
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/messages.md, specs/connect_core.md]
---

## Post

A customer photographs the damaged pallet and texts it to your service line. Where does that photo end up? 📷

In most setups: a phone that belongs to whoever was on shift.

In Oduist Connect it ends up on the message record, and it plays there:

🖼️ The **Media** field renders inbound MMS content inline — an image viewer for pictures, an audio player for voice clips
🔗 The message is linked to the partner, so the photo sits in the same history as their calls and orders
📍 Incoming SMS may also carry geographic hints — city, state, ZIP, country
🔎 It's an ordinary Odoo record: searchable, filterable, attachable to a lead or a ticket
🚫 No forwarding chain, no "can you WhatsApp me that picture again"

The unglamorous version of good software: the evidence lands where the work happens, and someone can find it six months later.

What's the piece of customer context that most often gets stranded on a personal phone in your team? 👇

#Odoo #MMS #CustomerService #FieldService #CRM

## Card

```json
{
  "template": "dialog",
  "kicker": "Oduist Connect · MMS",
  "headline": "They text a photo.",
  "headline_grad": "Odoo plays it inline.",
  "lede": "Inbound MMS media renders *on the message record* — image viewer or audio player — linked to the contact, next to their calls.",
  "bubbles": [
    {"side": "left", "who": "Customer · MMS", "text": "\"Pallet arrived like this.\" [photo attached]"},
    {"side": "right", "who": "Odoo · connect.message", "text": "Media field renders the image inline · partner matched by number · stored in the shared ledger"}
  ],
  "badge": "🖼 Image & audio players built into the message form",
  "footer": "connect.message · media widget · searchable like any Odoo record"
}
```

## Notes

Media rendering is a computed widget on `connect.message` (image/audio). Don't
promise video preview — the docs only mention image and audio.
