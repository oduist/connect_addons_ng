---
id: G8
title: Manual recording when auto is off
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/recordings.md, connect/docs/user/calls.md]
---

## Post

"We can't record everything — legal said no." Fine. That's an argument for *consent*, not for switching recording off entirely. ⚖️

In **Oduist Connect**, those are two different controls:

🔴 **Record Calls** (per user) governs *automatic* recording — leave it off
🎙️ The **REC** button in the phone widget stays available anyway. Ask the caller, get a yes, press it
⏹️ A purple stop icon appears only while audio is genuinely being captured — press it and recording stops
📼 The result lands on the call record with an inline player, like any other recording
🤖 And it flows into the same pipeline: Whisper transcript, AI summary, posted to the partner's chatter

Per-call flow recording exists too, for the flows where recording is always appropriate.

The setting controls what happens by default. It doesn't decide whether this particular call may be recorded — the agent and the caller do.

How does your team handle recording consent today? 👇

#Odoo #CallRecording #Compliance #GDPR #Telephony

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · Recording",
  "headline": "Auto off.",
  "headline_grad": "Button still there.",
  "lede": "*Record Calls* governs automatic recording only — the manual REC button stays usable on every answered call.",
  "columns": ["Automatic", "Manual button"],
  "rows": [
    {"f": "Starts without the agent acting", "m": ["✓", "—"]},
    {"f": "Available when Record Calls is off", "m": ["—", "✓"]},
    {"f": "Consent asked before it starts", "m": ["—", "✓"]},
    {"f": "Lands on the call with a player", "m": ["✓", "✓"]},
    {"f": "Transcribed & summarised by AI", "m": ["✓", "✓"]}
  ],
  "footer": "Per-user & per-call-flow settings · in-call REC control"
}
```

## Notes

In-call recording control requires a provider that supports runtime recording
control; the widget shows the button only then.
