---
id: I08
title: Masked secrets in Connect
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/admin/security.md, connect_twilio/docs/webhooks-security.md, connect_s3/docs/setup.md, specs/connect_core.md]
---

## Post

Here's an uncomfortable audit question: how many people in your Odoo can read your carrier's auth token right now? ⚠️

In **Oduist Connect**, "administrator of the phone system" and "person who can read the secrets" are two different roles:

🎭 OpenAI API key, Twilio Auth Token and API Secret render as `****` for anyone who is not an ERP Manager (`base.group_erp_manager`) — including a Connect Admin who configures numbers and call flows every day
🪣 The AWS secret access key on the S3 page is stored the same way
🔌 The masking isn't only in the form: `get_param` over RPC refuses parameters whose field carries a group restriction, so a plain user can't read a secret through the API either
🧾 Debug payloads are redacted too — Telnyx short-lived download URLs never get persisted into the debug log

Configuration rights and secret-reading rights should never be the same checkbox.

Where do your integration keys live — and who can actually see them? 👇

#Odoo #Security #SecretsManagement #ERP

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · Security",
  "headline": "Runs the phone system.",
  "headline_grad": "Still can't read the key.",
  "lede": "Protected fields render as `****` for everyone below *ERP Manager* — form and RPC alike.",
  "columns": ["Connect User", "Connect Admin", "ERP Manager"],
  "rows": [
    {"f": "Call, message, see own history", "m": ["✓", "✓", "✓"]},
    {"f": "Configure numbers & call flows", "m": ["—", "✓", "✓"]},
    {"f": "Open the Settings form", "m": ["—", "✓", "✓"]},
    {"f": "Read the OpenAI API key", "m": ["—", "—", "✓"]},
    {"f": "Read Twilio Auth Token / Secret", "m": ["—", "—", "✓"]},
    {"f": "Read a secret via get_param RPC", "m": ["—", "—", "✓"]}
  ],
  "footer": "Masked fields · group-restricted get_param · redacted debug payloads"
}
```

## Notes

Be precise in replies: masking is tied to `base.group_erp_manager`, not to
Connect Admin. Service tokens (firewall, FreeSWITCH webhook) are protected the
same way and are read through an administrative shell during deployment.
