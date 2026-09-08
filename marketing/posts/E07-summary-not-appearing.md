---
id: E07
title: Why isn't my AI summary appearing?
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/admin/core-setup.md]
---

## Post

"Transcription is enabled, the API key works, the recording is there — and no summary. Is it broken?" 🔍

Nine times out of ten it isn't. It's a disabled cron.

⏰ Transcription in **Oduist Connect** is driven by the *Connect: transcribe pending recordings* scheduled action, every two minutes
🧪 Sanitized copies — staging, test, restored backups — routinely ship with all scheduled actions switched off
✅ Fix: activate the scheduled action, and the queued recordings are picked up on the next run
▶️ In a hurry? The **Transcribe** button on a recording runs it now, and takes that recording out of the queue so it isn't sent to OpenAI twice
🧾 Still nothing? Check the OpenAI key and look at the transcription error on the recording

A pipeline you can inspect beats a black box you have to trust.

What's your favourite "it was just the cron" story? 👇

#Odoo #Troubleshooting #AI #OpenAI #DevOps

## Card

```json
{
  "template": "dialog",
  "accent": "purple",
  "kicker": "Oduist Connect · Support",
  "headline": "No summary?",
  "headline_grad": "Check the cron.",
  "lede": "Transcription runs on a *scheduled action every two minutes* — and sanitized staging databases usually ship with crons disabled.",
  "bubbles": [
    {"side": "left", "who": "Admin", "text": "\"Transcription is on, the key works, the recording is right there — but no transcript and no summary.\""},
    {"side": "right", "who": "Connect", "text": "\"Open Scheduled Actions: 'Connect: transcribe pending recordings' is inactive. Enable it — the queue is picked up on the next run. Or hit Transcribe on the recording to run it now.\""}
  ],
  "badge": "✓ Queued recordings processed on the next run",
  "footer": "Asynchronous by design · manual runs leave the queue clean"
}
```

## Notes

"Nine times out of ten" is rhetorical, not a measured statistic — soften it if
review prefers strictly factual phrasing.
