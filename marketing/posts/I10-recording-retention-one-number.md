---
id: I10
title: Recording retention as one number
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_s3/docs/setup.md]
---

## Post

"How long do you keep call recordings?" 🗓️

That question comes from an auditor, a customer or your own DPO — and "we're not sure, they're on the carrier somewhere" is the wrong answer.

With **Oduist Connect** + S3 storage, it's a single field:

🔢 **Retention (days)** on the S3 Storage page. `0` keeps audio forever; any other value installs an S3 **lifecycle rule** on your bucket
☁️ The deletion is executed by AWS on your own bucket — not by an Odoo cron you have to keep alive
🧠 Only the audio goes. The recording row, its transcript and its GPT summary stay in Odoo, so the business record survives the retention policy
▶️ After expiry the player shows **Recording expired**, and a playback request answers HTTP 410 instead of an error page
🔒 The bucket is provisioned with all public access blocked and SSE-S3 encryption at rest

Your bucket, your region, your number of days.

What's your recording retention today — and can you point at where it's enforced? 👇

#Odoo #DataRetention #S3 #Telephony #Compliance

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · S3 Storage",
  "headline": "Retention is one",
  "headline_grad": "number in a form.",
  "lede": "Twilio writes recordings into *your* bucket; an S3 lifecycle rule deletes the audio after N days.",
  "nodes": [
    {"t": "Twilio", "s": "writes recordings directly", "c": "provider"},
    {"t": "Your S3 bucket", "s": "SSE-S3 · no public access", "c": "core"},
    {"t": "Odoo", "s": "playback · transcript · summary", "c": "app"}
  ],
  "link_label": "your AWS account",
  "footer": "Lifecycle rule enforced by AWS · transcript & summary kept"
}
```

## Notes

Describe the mechanism only — we hold no documented compliance certification.
Mixed mode caveat for replies: recordings created before the switch stay on
Twilio and are not covered by the bucket lifecycle rule.
