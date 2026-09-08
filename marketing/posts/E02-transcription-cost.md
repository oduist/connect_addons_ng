---
id: E02
title: What AI call transcription actually costs
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/admin/core-setup.md, connect/docs/user/recordings.md]
---

## Post

"AI transcription for every call" sounds like a line item nobody can forecast. So we made it a field you can sum. 💵

Every recording in **Oduist Connect** carries a **Transcription Price** — the estimated Whisper speech-to-text cost in USD, based on the duration OpenAI actually processed:

📊 Stored per recording, so you can group, filter and total it in a list view
🔑 Billed on *your* OpenAI key — we don't resell tokens or add a per-minute markup
🎚️ Transcription is a switch: turn it on for the whole system, or trigger it by hand on a single recording
♻️ The manual **Transcribe** button pulls the recording out of the automatic queue, so nothing is sent to OpenAI twice

Cost control isn't a promise here — it's a column.

Would per-call AI cost visibility change how much of it you'd switch on? 👇

#Odoo #AI #OpenAI #Telephony #CostControl

## Card

```json
{
  "template": "thesis",
  "accent": "purple",
  "kicker": "Oduist Connect · AI",
  "headline": "AI cost per call,",
  "headline_grad": "as an Odoo field.",
  "lede": "Every recording stores its *estimated Whisper cost in USD* — group it, filter it, total it like any other number in Odoo.",
  "tiles": [
    {"sym": "$", "nm": "Price field", "c": "purple", "hero": true},
    {"sym": "⏱", "nm": "Processed time", "c": "cyan"},
    {"sym": "🔑", "nm": "Your API key", "c": "app"},
    {"sym": "⇄", "nm": "No markup", "c": "app"},
    {"sym": "▶", "nm": "Manual run", "c": "provider"},
    {"sym": "≠", "nm": "No double send", "c": "core"}
  ],
  "footer": "Transcription Price · estimated Whisper cost in USD per recording"
}
```

## Notes

The price is an *estimate* from OpenAI's processed duration — never present it as
an invoice-grade figure in replies.
