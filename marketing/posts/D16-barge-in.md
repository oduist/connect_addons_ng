---
id: D16
title: Barge-in and Protect Greeting
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/ai-agents.md, connect_pipecat/docs/admin/pipecat-setup.md, connect_telnyx/docs/admin/telnyx-setup.md]
---

## Post

Nothing makes a voice agent feel like a machine faster than not being able to interrupt it. 🤖

We have all been held hostage by a menu reading nine options while we knew we wanted option three by second two.

Barge-in fixes that — and it is a configuration decision, not magic:

✂️ Start speaking and the agent stops playback mid-sentence and processes your new turn instead of finishing its paragraph
🔇 Protect Greeting is the deliberate exception: speech is ignored until the greeting has finished, so a background "hello" doesn't kill the opening line
🎚️ Caller Can Interrupt is an explicit per-agent switch, not a vendor default you inherit
🧪 On self-hosted Pipecat it is part of the acceptance test — talk over a long reply, playback must stop immediately
🔧 On your own FreeSWITCH the interrupt travels as a killAudio down the media stream, and it is a logged, debuggable event

Nobody will ever compliment your barge-in. They will just stop dreading the phone menu.

When did an automated system last refuse to let you speak? 👇

#Odoo #VoiceAI #IVR #CustomerExperience #AI

## Card

```json
{
  "template": "dialog",
  "accent": "purple",
  "kicker": "Oduist Connect · AI Agents",
  "headline": "Let the caller",
  "headline_grad": "cut the AI off.",
  "lede": "Barge-in stops playback mid-sentence — while *Protect Greeting* keeps the opening line intact.",
  "bubbles": [
    {"side": "right", "who": "AI Agent", "text": "\"Of course, I can check that for you. Our support team is available Monday to Friday, and if you'd prefer I can also send you—\""},
    {"side": "left", "who": "Caller · interrupts", "text": "\"Just book me for Thursday morning.\""},
    {"side": "right", "who": "AI Agent", "text": "\"Thursday morning — let me find a slot.\""}
  ],
  "badge": "✓ Playback stopped mid-word · new turn processed",
  "footer": "Barge-in + Protect Greeting · verified on every deployment"
}
```

## Notes

"Protect Greeting" and "Caller Can Interrupt" are named settings in the Telnyx
assistant docs (Turn Taking group), so telnyx-setup.md is cited even though the
brief listed only ai-agents.md and pipecat-setup.md. The killAudio detail is the
Pipecat/FreeSWITCH path specifically — do not generalise it to all providers.
