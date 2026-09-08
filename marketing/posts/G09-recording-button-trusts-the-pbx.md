---
id: G9
title: The recording button trusts the PBX
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/recordings.md]
---

## Post

A recording button that lies to you is worse than no button at all. 🔴

Here's the trap. Automatic recording only starts when the far end picks up, and the provider needs another moment to report it. So a naive UI sits on *Start Recording* for the first several seconds of a call that is, in fact, already being recorded. An agent presses it. Now they've stopped the recording they thought they were starting.

**Oduist Connect** does it the other way round:

🧠 The button shows what the **phone system reports**, not what the settings imply
⚡ It's usable from the moment the call is answered — no dead first seconds
🎯 It starts optimistic: Record Calls on for you? It shows *Stop Recording* immediately
🔄 Then the provider answers for real, and the button corrects itself — silently settling back to *Start Recording* if the call turned out not to be recorded
♻️ One state for all sources: call flow, per-user setting, or manual — stopping stops whichever is running

Optimistic UI, corrected by the source of truth. Which is how in-call controls should behave.

#Odoo #CallRecording #UX #Telephony #SoftwareDesign

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Recording",
  "headline": "The button trusts",
  "headline_grad": "the PBX, not settings.",
  "lede": "Optimistic state on answer, then *corrected by the provider* — one truth for auto, call-flow and manual recording.",
  "tiles": [
    {"sym": "0s", "nm": "Usable on answer", "c": "cyan"},
    {"sym": "⏺", "nm": "Optimistic state", "c": "memory"},
    {"sym": "↺", "nm": "Provider corrects", "c": "app", "hero": true},
    {"sym": "⚙", "nm": "Per-user auto", "c": "provider"},
    {"sym": "🌳", "nm": "Call flow", "c": "provider"},
    {"sym": "✋", "nm": "Manual REC", "c": "magenta"}
  ],
  "footer": "One state · stops whichever recording is actually running"
}
```

## Notes

Behaviour is documented in recordings.md, "In-Call Recording Control". Available
where the provider supports runtime recording control.
