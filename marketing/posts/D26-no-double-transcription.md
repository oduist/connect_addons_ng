---
id: D26
title: Never transcribe an AI call twice
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_elevenlabs/docs/maintenance.md, connect_telnyx/docs/admin/telnyx-setup.md]
---

## Post

There is an easy way to double an AI bill: transcribe a conversation that has already been transcribed. 🧾

When an AI agent handles a call, the vendor produced a full transcript as a by-product of holding the conversation. Shipping that same audio to OpenAI afterwards buys you a second copy and a second invoice.

So Oduist Connect doesn't:

🚫 A Telnyx assistant call is stored with the Telnyx transcript and insight summary, and the audio is never sent for a second transcription — even with global call transcription switched on
🚫 ElevenLabs post-call webhooks write the vendor transcript and summary straight onto the recording, with transcription explicitly skipped
✅ Everything downstream still fires: the transcript appears on the call form and hooks such as Oduist Memory run exactly as they would otherwise
🎚️ The summary stays yours — its wording is a prompt you configure in Odoo settings, not a vendor default
🔁 Ordinary human calls are untouched and still go through the core transcription and GPT summary pipeline

A good integration is mostly a list of things it deliberately refuses to do twice.

Where is your stack quietly paying for the same work twice? 👇

#Odoo #VoiceAI #Integration #FinOps #AI

## Card

```json
{
  "template": "comparison",
  "accent": "purple",
  "kicker": "Oduist Connect · AI Agents",
  "headline": "Never pay twice",
  "headline_grad": "for the same words.",
  "lede": "The AI vendor already transcribed the call — Connect *stores that transcript* instead of buying a second one.",
  "columns": ["Naive wiring", "Connect"],
  "rows": [
    {"f": "Vendor transcript on the call", "m": ["✓", "✓"]},
    {"f": "Skips duplicate transcription", "m": ["—", "✓"]},
    {"f": "Summary in the same record", "m": ["—", "✓"]},
    {"f": "Downstream hooks still fire", "m": ["—", "✓"]},
    {"f": "Human calls still transcribed", "m": ["✓", "✓"]}
  ],
  "footer": "Telnyx & ElevenLabs transcripts reused · core pipeline for the rest"
}
```

## Notes

Do not attach a cost saving to this — the docs state the behaviour, not a
figure. ElevenLabs can also be selected as the transcript provider for ordinary
recordings (Scribe v1 with diarization); that is a different path from the
post-call transcript reuse described here.
