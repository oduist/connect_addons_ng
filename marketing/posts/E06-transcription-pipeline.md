---
id: E06
title: The transcription pipeline, step by step
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/admin/core-setup.md]
---

## Post

Here is everything that happens in the two minutes after you hang up — with nobody touching a keyboard. ⏱️

The **Oduist Connect** transcription pipeline, in order:

1️⃣ The recording is created and queued
2️⃣ The *Connect: transcribe pending recordings* scheduled action runs — every two minutes
3️⃣ Audio goes to OpenAI Whisper for speech-to-text
4️⃣ The estimated cost is stored from the duration OpenAI processed
5️⃣ The transcript goes to your chosen model with your summary prompt
6️⃣ Transcript and summary are saved permanently on the call
7️⃣ Optionally the recording is deleted, and the summary is posted to the chatter

Why a cron and not the web request? Because transcription is asynchronous by design — a slow OpenAI call must never hold up a webhook from your carrier or block a live call.

Where does your call data go to die today? 👇

#Odoo #AI #OpenAI #Telephony #Automation

## Card

```json
{
  "template": "thesis",
  "accent": "purple",
  "kicker": "Oduist Connect · Pipeline",
  "headline": "Hang up.",
  "headline_grad": "The rest is a cron.",
  "lede": "Seven steps from audio to a summary in the chatter — *asynchronous by design*, so no webhook ever waits on OpenAI.",
  "tiles": [
    {"sym": "1", "nm": "Queue", "c": "cyan"},
    {"sym": "2", "nm": "Cron 2 min", "c": "cyan", "hero": true},
    {"sym": "3", "nm": "Whisper", "c": "purple"},
    {"sym": "4", "nm": "Price", "c": "memory"},
    {"sym": "5", "nm": "Summary", "c": "purple"},
    {"sym": "6", "nm": "Saved", "c": "app"},
    {"sym": "7", "nm": "Chatter", "c": "app"},
    {"sym": "8", "nm": "Cleanup", "c": "core"},
    {"sym": "∞", "nm": "Kept on call", "c": "provider"}
  ],
  "footer": "Connect: transcribe pending recordings · runs every two minutes"
}
```

## Notes

Steps 6–8 in the card compress the doc's steps 6–8 (save / optional delete /
optional chatter post); the post text keeps the documented order.
