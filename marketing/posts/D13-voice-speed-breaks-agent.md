---
id: D13
title: Voice cloning, speed, and the setting that kills every call
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/ai-agents.md, connect_telnyx/docs/admin/telnyx-setup.md]
---

## Post

⚠️ The nastiest failure in voice AI: the agent answers, then hangs up after about one second. Every call. And nothing looks broken.

The usual cause is one number. **Voice Speed.**

What we learned the hard way in **Oduist Connect** with Telnyx:

🎚️ Speed is constrained to **0.5–1.5**, and `1.0` is the safe default
🚫 Telnyx documents a wider range for Natural voices only — another voice simply rejects a speed it doesn't support. Telnyx Ultra needs at least 0.8
🕵️ The rejection is invisible until a real call arrives: the agent answers, can't synthesize its greeting, and drops
🔊 So there's a speaker button next to the Voice field. It plays a sample **at the configured speed**, through the same endpoint the greeting uses — a bad voice/speed pair fails in the form, not on a call
🎭 Voices come from your account catalogue by name, gender or ID; cloned ones show as *Callie*, not `Telnyx.Ultra.00a77add-…`
🩺 If it does reach production, the call form's **Error** tab carries the provider's reason — otherwise it just looks like a very short chat

Press the sample button. Every time.

What's your favourite silent-failure bug? 👇

#VoiceAI #Odoo #Telnyx #AIAgents

## Card

```json
{
  "template": "dialog",
  "accent": "purple",
  "kicker": "Oduist Connect · Voice Settings",
  "headline": "Answered. Then dead",
  "headline_grad": "after one second.",
  "lede": "A voice that rejects your speed setting can't synthesize the greeting. *Play the sample before you save* — same endpoint, same failure.",
  "bubbles": [
    {"side": "left", "who": "Caller", "text": "\"Hello? ...\""},
    {"side": "right", "who": "AI Agent", "text": "— call ended after ~1 second —"}
  ],
  "badge": "⚠ Voice Speed must be 0.5–1.5 · Telnyx Ultra needs ≥ 0.8",
  "footer": "Sample button validates voice + speed · Error tab shows the reason"
}
```

## Notes

Range differs by provider: Telnyx enforces **0.5–1.5** (ADR-057), while the
ElevenLabs agent form validates speed **0.7–1.2**. This post is scoped to
Telnyx — do not quote 0.5–1.5 for an ElevenLabs agent.
