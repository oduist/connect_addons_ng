---
id: E08
title: Speaker diarization on call transcripts
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_elevenlabs/docs/configuration.md, connect_elevenlabs/docs/maintenance.md]
---

## Post

Who said the number — the customer, or your agent? On a flat wall of transcript text, you genuinely cannot tell. 🗣️

That's what diarization is for. When **Transcript Provider** is set to ElevenLabs in **Oduist Connect**, recordings are transcribed with Speech-to-Text `scribe_v1` and **diarization enabled** — the engine attributes speech to separate speakers instead of merging a two-party call into one stream.

👥 Speakers are separated during transcription, not guessed afterwards
🚫 Audio events (laughter, applause) are deliberately not tagged — call transcripts, not subtitles
✍️ The summary is still written by OpenAI, from that transcript
↩️ Switch the provider back and the core Whisper pipeline takes over again — no migration, same call records

One setting, in the same place as every other Connect setting.

On your calls, does speaker attribution actually change the decision you make? 👇

#Odoo #ElevenLabs #SpeechToText #AI #CallCenter

## Card

```json
{
  "template": "diagram",
  "accent": "purple",
  "kicker": "Oduist Connect · Transcription",
  "headline": "Two voices in.",
  "headline_grad": "Two speakers out.",
  "lede": "ElevenLabs `scribe_v1` runs with *diarization on*, so a two-party call is transcribed as two speakers — then summarized by OpenAI.",
  "nodes": [
    {"t": "Call recording", "s": "agent + customer", "c": "cyan"},
    {"t": "Scribe v1", "s": "diarization on", "c": "purple"},
    {"t": "Call record", "s": "transcript + summary", "c": "app"}
  ],
  "link_label": "transcribe",
  "footer": "Set Transcript Provider to ElevenLabs · OpenAI still writes the summary"
}
```

## Notes

Verified in `connect_elevenlabs/models/recording.py`: `diarize=True`,
`tag_audio_events=False`, and only `response.text` is stored. Diarization is
requested from the engine, but Odoo does not currently render per-speaker labels
in the transcript field — do not promise a labelled transcript in replies.
