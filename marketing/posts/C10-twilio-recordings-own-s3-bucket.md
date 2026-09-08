---
id: C10
title: Store Twilio call recordings in your own S3 bucket
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_s3/docs/index.md, connect_s3/docs/setup.md]
---

## Post

You're paying Twilio to store recordings of your own phone calls, under a retention policy you don't control. 💾

**Oduist Connect S3** moves them into your own AWS bucket — Twilio writes them there directly, Odoo just reads them back:

🪣 Odoo generates the scoped IAM policy, then creates the bucket for you: public access blocked, SSE-S3 encryption at rest, lifecycle rule installed
🔐 It also registers the AWS credential with Twilio, so you never paste AWS keys into the Twilio Console
🗓️ Set retention in days (`0` keeps audio forever). When a file expires, the player says *Recording expired* — the transcript and the AI summary stay
🔀 Mixed mode is fine: recordings made before the switch keep playing from Twilio. No migration, both kinds coexist
⚠️ One manual step survives — Twilio exposes recording settings in the Console only, so you flip external storage on there once

Your compliance team gets a retention rule they can point at. You get one less storage line on the invoice.

Where do your call recordings actually live? 👇

#Odoo #Twilio #AWS #S3 #DataRetention

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · S3 Storage",
  "headline": "Your recordings,",
  "headline_grad": "your bucket.",
  "lede": "Twilio External S3 Storage, provisioned from Odoo: *bucket, IAM policy, encryption and lifecycle rule* in a few clicks.",
  "columns": ["Twilio storage", "Your S3"],
  "rows": [
    {"f": "Audio stored in your own account", "m": ["—", "✓"]},
    {"f": "Retention rule you control", "m": ["—", "✓"]},
    {"f": "No provider storage bill", "m": ["—", "✓"]},
    {"f": "Transcript kept after audio expires", "m": ["—", "✓"]},
    {"f": "Playback inside the call record", "m": ["✓", "✓"]},
    {"f": "AI transcript & summary", "m": ["✓", "✓"]}
  ],
  "footer": "Bucket + IAM policy provisioned from Odoo · pre-switch recordings keep playing"
}
```

## Notes

Important caveat for replies: once external storage is on, the audio is no
longer fetchable from Twilio — if the AWS credentials in Odoo stop working,
playback stops. Key rotation needs re-selecting the new credential in the
Twilio Console.
