---
id: E04
title: Keep the transcript, delete the audio
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/admin/core-setup.md, connect/docs/user/recordings.md]
---

## Post

Your DPO doesn't object to call analytics. They object to a folder of voice recordings sitting there forever. 🔒

**Oduist Connect** separates the two. Switch on *Delete Recording After Transcription* and:

🗑️ The Odoo recording row and its Odoo-managed attachment are removed
📄 The transcript and the AI summary stay on the call record permanently
✅ Deletion only fires for recordings linked to a call, and only after transcription *and* summarization succeeded
🛟 Failed or unlinked recordings are kept, so nothing disappears silently
⚙️ It's off by default — you turn it on deliberately

One caveat we say out loud: this governs the audio Odoo holds. Retention on the provider side is configured separately, with your carrier.

Voice data retention: how long does your policy actually allow? 👇

#Odoo #GDPR #DataRetention #CallRecording #AI

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · Compliance",
  "headline": "Keep the transcript.",
  "headline_grad": "Drop the audio.",
  "lede": "*Delete Recording After Transcription* removes the voice file from Odoo — the searchable text stays.",
  "columns": ["Audio kept", "Audio deleted"],
  "rows": [
    {"f": "Full transcript on the call", "m": ["✓", "✓"]},
    {"f": "AI summary in the chatter", "m": ["✓", "✓"]},
    {"f": "Searchable call history", "m": ["✓", "✓"]},
    {"f": "Voice file stored in Odoo", "m": ["✓", "—"]},
    {"f": "In-browser playback", "m": ["✓", "—"]},
    {"f": "Deletes on failed jobs", "m": ["—", "—"]}
  ],
  "footer": "Off by default · provider-side audio retention is configured separately"
}
```

## Notes

Do not call this "GDPR compliance" in replies — it is a retention control that
helps implement a policy. Provider-side retention is out of scope.
