---
id: E01
title: Every call summarized automatically
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/recordings.md, connect/docs/admin/core-setup.md]
---

## Post

Nobody writes call notes. They write *"called client, will follow up"* — three days later, from memory. 📝

**Oduist Connect** removes that step entirely. When a recorded call ends:

⏺️ The recording lands in the transcription queue
🗣️ OpenAI Whisper turns the audio into a full transcript
🤖 An OpenAI model (GPT-5.4 mini by default) writes the summary
📌 Transcript and summary are stored permanently on the call record
💬 With *Register Summary* on, the summary is posted to the contact's chatter — and to the linked lead, ticket, sale order, invoice, task or employee

No plugin, no separate dashboard, no copy-paste. The gist of the conversation is already on the record when your colleague opens it.

How does your team log calls today — CRM notes, a spreadsheet, or nothing at all? 👇

#Odoo #AI #CRM #CallRecording #Whisper

## Card

```json
{
  "template": "diagram",
  "accent": "purple",
  "kicker": "Oduist Connect · AI",
  "headline": "Every call ends",
  "headline_grad": "as a written summary.",
  "lede": "Whisper transcribes, an OpenAI model summarizes, and the result is posted to the *chatter of the linked record* — automatically.",
  "nodes": [
    {"t": "Recorded call", "s": "any Connect provider", "c": "cyan"},
    {"t": "Whisper + GPT", "s": "transcript & summary", "c": "purple"},
    {"t": "Odoo chatter", "s": "contact · lead · ticket", "c": "app"}
  ],
  "link_label": "automatic",
  "footer": "Transcript and summary stay on the call record permanently"
}
```

## Notes

The default summary model name (GPT-5.4 mini) comes from the core settings doc —
re-check it before publishing in case the default moved.
