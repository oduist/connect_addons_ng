---
id: I06
title: Least privilege for telephony webhooks
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/admin/security.md, connect_sale/docs/security.md, connect_hr/docs/security.md, connect_account/docs/security.md, connect_project/docs/security.md]
---

## Post

Assume the worst for a second: someone gets a valid request through your webhook endpoint. What can it actually do? 🎯

That question is why **Oduist Connect** webhook controllers do not run as an administrator. They run as a dedicated, inactive Odoo user (`connect.user_connect_webhook`) in the Connect Webhook group — and that identity is deliberately boring:

📖 Read-only access to `sale.order`, `hr.employee`, `account.move`, `project.task` and `project.project` — no create, no write, no unlink
🔗 It only links existing records to a call; it never creates an order, an employee or an invoice
🚫 No access to Connect settings at all — masked secrets are never handed to it
👤 Buttons and Unlink actions on the call form run as the logged-in user, with that user's own Sales / HR / Accounting rights

Least privilege isn't a slogan here, it's a table of `ir.model.access` rows you can read.

What's the widest permission an integration holds in your Odoo right now? 👇

#Odoo #Security #Integration #ERP #LeastPrivilege

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Security",
  "headline": "The webhook user",
  "headline_grad": "can barely do anything.",
  "lede": "Public controllers run as a dedicated identity with *read-only* rights on every business model they touch.",
  "tiles": [
    {"sym": "R", "nm": "sale.order · read only", "c": "app"},
    {"sym": "R", "nm": "hr.employee · read only", "c": "app"},
    {"sym": "R", "nm": "account.move · read only", "c": "app"},
    {"sym": "R", "nm": "project.task · read only", "c": "app"},
    {"sym": "RWC", "nm": "connect.call · link events", "c": "provider", "hero": true},
    {"sym": "—", "nm": "connect.settings · none", "c": "core"}
  ],
  "footer": "connect.user_connect_webhook · inactive user · connect.group_webhook"
}
```

## Notes

`connect.twilio.outgoing_callerid` and `connect.whatsapp_sender` are the
exceptions where the webhook identity also gets write/create — don't claim
"read-only everywhere" without that caveat.
