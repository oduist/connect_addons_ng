---
id: J01
title: Recording plays as 0 seconds
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_twilio/docs/maintenance.md]
---

## Post

"The call is right there in Odoo — duration, cost, caller — but the recording plays as 0 seconds." ⏱️

We get this one a lot. The metadata is correct, because it comes from the Twilio API. The audio simply never arrived.

Playback goes through Odoo's media proxy: the player asks Odoo for the file, Odoo fetches it. The usual cause is **External Storage** on the Twilio account (Voice → Settings → Recording storage). Twilio writes the audio into your own S3 bucket and keeps only the metadata — so the API no longer serves the file, and the bucket rejects an unauthenticated read.

Two fixes: turn External Storage off, or install **`connect_s3`**, which owns that setup and reads the audio back from the bucket.

What's your favourite "the metadata lied to me" bug? 👇

#Odoo #Twilio #AWS

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Troubleshooting",
  "headline": "Metadata is fine.",
  "headline_grad": "The audio isn't there.",
  "lede": "Twilio *External Storage* keeps only the metadata — the recording itself went straight into your own S3 bucket.",
  "nodes": [
    {"t": "Twilio API", "s": "duration · price · caller ID", "c": "provider"},
    {"t": "Your S3 bucket", "s": "the actual audio file", "c": "memory"}
  ],
  "link_label": "connect_s3",
  "footer": "Turn External Storage off — or install connect_s3 and read the bucket"
}
```

## Notes

Source is the "A recording plays as 0 seconds" section of
`connect_twilio/docs/maintenance.md` (ADR-060). Do not promise that `connect_s3`
recovers pre-switch recordings — mixed mode means older files stay on Twilio.
