---
id: E05
title: ElevenLabs Scribe as your transcription engine
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_elevenlabs/docs/configuration.md, connect_elevenlabs/docs/maintenance.md, connect/docs/admin/core-setup.md]
---

## Post

Whisper is the default in **Oduist Connect**. It is not the only option. 🎙️

Install the ElevenLabs integration and the core **Transcript Provider** setting gains a second choice — ElevenLabs Speech-to-Text (`scribe_v1`):

🔀 One dropdown switches the engine for recording transcription; everything downstream is unchanged
👥 Scribe runs with diarization on, so the engine separates the speakers instead of flattening the call
✍️ The summary is still written by OpenAI — summarization stays in the provider-agnostic core
↩️ Any other value falls straight back to the core Whisper pipeline
🤖 Calls handled by an ElevenLabs voice agent aren't transcribed twice: the post-call webhook stores the conversation transcript and summary directly

Two engines, one call ledger, zero migration. Your existing transcripts and summaries stay exactly where they are.

Which matters more on your calls: raw accuracy, or speaker separation? 👇

#Odoo #ElevenLabs #SpeechToText #AI #Telephony

## Card

```json
{
  "template": "comparison",
  "accent": "purple",
  "kicker": "Oduist Connect · Transcription",
  "headline": "Two engines.",
  "headline_grad": "One call ledger.",
  "lede": "*Transcript Provider* is a dropdown: OpenAI Whisper by default, ElevenLabs Scribe when the ElevenLabs module is installed.",
  "columns": ["Whisper", "Scribe"],
  "rows": [
    {"f": "Ships with core Connect", "m": ["✓", "—"]},
    {"f": "Needs ElevenLabs module", "m": ["—", "✓"]},
    {"f": "Diarization requested", "m": ["—", "✓"]},
    {"f": "OpenAI-written summary", "m": ["✓", "✓"]},
    {"f": "Per-recording cost field", "m": ["✓", "—"]},
    {"f": "Same call record & chatter", "m": ["✓", "✓"]}
  ],
  "footer": "Switch the engine in Connect settings — the pipeline around it stays the same"
}
```

## Notes

Transcription Price is documented as the estimated *Whisper* cost; do not claim a
cost figure for the Scribe path. The ElevenLabs path is license-gated — without a
valid license the core pipeline is used.
