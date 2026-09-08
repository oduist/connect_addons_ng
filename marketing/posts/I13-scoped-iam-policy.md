---
id: I13
title: A scoped IAM policy for recordings
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_s3/docs/setup.md]
---

## Post

Most "store your files in S3" integrations end the same way: paste an access key here, and trust us with what we do with it. 🙃

**Oduist Connect** hands you the policy instead of asking for the keys.

📋 The S3 Storage page generates a ready **IAM policy** scoped to your bucket prefix — every bucket name you type is forced to start with that prefix
🎯 It grants bucket create/configure and object read/write **under your prefix only**, and contains no `iam:*` permissions at all
🧱 One button provisions the bucket: all public access blocked, SSE-S3 encryption at rest, and the lifecycle rule if you set a retention. Safe to press again.
🔐 Odoo registers the key with Twilio as a named credential, so you never paste AWS keys into the Twilio Console — the secret stays masked in Odoo
🧭 If AWS answers *AccessDenied*, the error names the exact ARN to allow

You should be able to read an integration's permissions in under a minute. This one fits on a screen.

What's the widest IAM policy currently attached to a SaaS integration you own? 👇

#AWS #IAM #Odoo #Security #S3

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · S3 Storage",
  "headline": "A policy that can",
  "headline_grad": "only touch your bucket.",
  "lede": "Generated for *your* prefix, pasted into AWS once — no `iam:*`, no wildcards over your account.",
  "tiles": [
    {"sym": "S3", "nm": "bucket create & configure", "c": "provider"},
    {"sym": "RW", "nm": "objects under your prefix", "c": "provider"},
    {"sym": "⛔", "nm": "no iam:* permissions", "c": "core", "hero": true},
    {"sym": "🔒", "nm": "SSE-S3 at rest", "c": "app"},
    {"sym": "🚫", "nm": "public access blocked", "c": "app"},
    {"sym": "⏱", "nm": "lifecycle retention rule", "c": "cyan"}
  ],
  "footer": "Connect ▸ Configuration ▸ S3 Storage · key masked, registered with Twilio from Odoo"
}
```

## Notes

Rotation is a documented 4-step runbook; the last step (re-selecting the new
credential in the Twilio Console) is manual and easy to forget — mention it if
anyone asks about key rotation.
