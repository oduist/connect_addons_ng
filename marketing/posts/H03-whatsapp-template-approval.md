---
id: H03
title: Submit a WhatsApp template for approval from Odoo
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_telnyx/docs/admin/telnyx-setup.md, connect_infobip/docs/admin/infobip-setup.md, connect_twilio/docs/messaging.md]
---

## Post

Marketing writes the WhatsApp template. Someone logs into a provider portal, retypes it, submits it to Meta, then waits — and nobody in Odoo knows what happened to it. ✍️

Cut the portal out of that loop.

With **Oduist Connect on Telnyx or Infobip**:

📝 Create the template in Odoo — body text with `{{1}}`-style variables
🚀 Submit it for Meta approval with one click, from the same form
🔄 Sync pulls every template back with its approval status: unsubmitted, pending, approved, rejected, paused, disabled
🎯 On Infobip templates are per-sender, so each WABA number keeps its own set
💬 Approved templates then show up directly in the WhatsApp composer

On Twilio, templates are managed in the Twilio console and synced into Odoo read-side — the approval status still lands on the record.

Same rule everywhere: no approved template, no business-initiated message.

How long does a template take to clear approval in your account? 👇

#WhatsApp #Odoo #Telnyx #Infobip #BusinessMessaging

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · WhatsApp Templates",
  "headline": "Write the template.",
  "headline_grad": "Submit it from Odoo.",
  "lede": "Body text with `{{1}}` variables, one click to submit for Meta approval, and the *status syncs back* onto the record.",
  "nodes": [
    {"t": "Odoo", "s": "template editor & composer", "c": "app"},
    {"t": "Telnyx / Infobip", "s": "submit → Meta approval", "c": "provider"}
  ],
  "link_label": "Submit & sync",
  "footer": "Statuses: unsubmitted · pending · approved · rejected · paused · disabled"
}
```

## Notes

Submission from Odoo is documented for Telnyx and Infobip. Twilio is sync-only
(templates are created in the Twilio console) — keep that distinction if asked.
