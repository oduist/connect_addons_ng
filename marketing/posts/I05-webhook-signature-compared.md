---
id: I05
title: Webhook signatures compared
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_twilio/docs/webhooks-security.md, connect_telnyx/docs/admin/telnyx-setup.md, connect_bird/docs/admin/bird-setup.md, specs/connect_bird.md]
---

## Post

A telephony webhook URL is public by definition — your carrier has to reach it. So the only thing separating a real call event from a forged one is the signature check. 🔏

Three carriers, three schemes, all verified by **Oduist Connect** before a single record is written:

📞 **Twilio** — the `X-Twilio-Signature` header, validated with Twilio's `RequestValidator` against your Auth Token. The URL is forced to `https:` for the computation.
🔑 **Telnyx** — Ed25519 public-key signature: `telnyx-signature-ed25519` + `telnyx-timestamp`. The body is signed byte for byte, so a reverse proxy must not re-encode the form.
🐦 **Bird** — Standard Webhooks: `webhook-id` / `webhook-timestamp` / `webhook-signature`, HMAC-SHA256 with a `whsec_` secret and a configurable timestamp tolerance.

Verification is **on by default** on all three. When it fails, nothing is processed — voice routes answer with a plain "invalid request" and status routes simply return false.

The off switch exists for local debugging only. Does yours? 👇

#Odoo #Webhooks #Twilio #Telnyx #Security

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · Webhooks",
  "headline": "Three carriers.",
  "headline_grad": "Three signatures.",
  "lede": "Every inbound webhook is verified *before* it becomes a record — HMAC, Ed25519 or Standard Webhooks.",
  "columns": ["Twilio", "Telnyx", "Bird"],
  "rows": [
    {"f": "Signature checked on every webhook", "m": ["✓", "✓", "✓"]},
    {"f": "Shared-secret (HMAC) scheme", "m": ["✓", "—", "✓"]},
    {"f": "Public-key signature (Ed25519)", "m": ["—", "✓", "—"]},
    {"f": "Timestamp header in the scheme", "m": ["—", "✓", "✓"]},
    {"f": "Verification on by default", "m": ["✓", "✓", "✓"]},
    {"f": "Off switch = development only", "m": ["✓", "✓", "✓"]}
  ],
  "footer": "Public HTTPS API URL required · secrets masked for non-managers"
}
```

## Notes

Bird header names and HMAC-SHA256 come from `specs/connect_bird.md`; the setup
doc only names the Standard Webhooks scheme. Bird also cannot yet deliver
`sms.*` / `voice.*` events — statuses are polled. Don't imply live inbound Bird
webhooks in replies.
