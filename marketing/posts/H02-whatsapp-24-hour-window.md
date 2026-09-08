---
id: H02
title: The WhatsApp 24-hour window explained
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/messages.md, connect_telnyx/docs/admin/telnyx-setup.md, connect_bird/docs/admin/bird-setup.md, connect_infobip/docs/admin/infobip-setup.md]
---

## Post

"The WhatsApp message just failed. Nothing changed on our side." 🤔

Something did change: the clock ran out.

WhatsApp splits every conversation in two modes, and Oduist Connect follows the rule instead of hiding it:

⏱️ **Inside 24 hours** of the customer's last message — you can send free-form text, type whatever you want
📋 **Outside it, or on first contact** — you must pick an approved message template
🧩 Templates carry variables (`{{1}}`, `{{2}}`), a category (utility, authentication, marketing) and a language
✅ Only templates with an *approved* status can be used for business-initiated messages
🔁 Every provider we support behaves this way — Twilio, Telnyx, Infobip and Bird alike. It's Meta's rule, not the vendor's

So a "sudden" WhatsApp failure is usually a closed window, not a broken integration.

Which of your customer messages are template-worthy — order updates, delivery ETAs, appointment reminders? 👇

#WhatsApp #Odoo #CustomerService #BusinessMessaging

## Card

```json
{
  "template": "dialog",
  "kicker": "Oduist Connect · WhatsApp",
  "headline": "24 hours to reply.",
  "headline_grad": "Then a template.",
  "lede": "Inside the customer window you type freely. Outside it, WhatsApp only accepts an *approved template* — Connect picks the right mode for you.",
  "bubbles": [
    {"side": "left", "who": "Customer · 09:12", "text": "\"Hi — where is order S00142?\""},
    {"side": "right", "who": "You · 09:14 · free-form", "text": "\"It ships today, tracking follows this afternoon.\""},
    {"side": "right", "who": "You · next day · template", "text": "\"Your order {{1}} was delivered on {{2}}.\" — approved template required"}
  ],
  "badge": "⏱ Window closed → free-form text is rejected",
  "footer": "Meta's rule, enforced by Twilio, Telnyx, Infobip and Bird alike"
}
```

## Notes

Do not present the 24-hour window as an Oduist feature — it is a Meta platform
rule. Connect's part is surfacing it in the composer.
