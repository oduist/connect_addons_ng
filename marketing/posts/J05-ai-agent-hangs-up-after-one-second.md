---
id: J05
title: AI agent hangs up after one second
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_telnyx/docs/admin/telnyx-setup.md, connect/docs/user/ai-agents.md]
---

## Post

The call connects. Then silence. Then it's over — about one second in, every single time. 🎙️

The cause is almost always **voice speed**. Telnyx documents a wide speed range for its Natural voices only; other voices reject a speed they don't support, and that failure is invisible until a real call arrives. The assistant answers, cannot synthesize its greeting, and hangs up.

The fix: put **Voice Speed** back to `1.0` (the field is constrained to 0.5–1.5; Telnyx Ultra needs at least 0.8). Then check the assistant conversation in the Telnyx portal for *"could not generate the greeting audio"*.

Two things make this catchable: the **speaker button** next to the Voice field validates that exact voice + speed pair before you save, and the call form shows an **Error** tab with the provider's reason.

What's your one-second-call story? 👇

#Odoo #VoiceAI #Telnyx

## Card

```json
{
  "template": "dialog",
  "accent": "purple",
  "kicker": "Oduist Connect · AI Agents",
  "headline": "Answered. Silent.",
  "headline_grad": "Gone in a second.",
  "lede": "A voice that rejects the configured speed cannot render the greeting — and the assistant ends the call *before it says anything*.",
  "bubbles": [
    {"side": "left", "who": "Caller", "text": "\"Hello?\" — line drops one second after pickup"},
    {"side": "right", "who": "Telnyx conversation", "text": "could not generate the greeting audio"}
  ],
  "badge": "✓ Fix: Voice Speed 1.0 — Telnyx Ultra needs at least 0.8",
  "footer": "Play the voice sample before saving · Error tab shows the provider reason"
}
```

## Notes

Speed range and the Ultra ≥ 0.8 detail come from the Telnyx setup doc
(ADR-057). The Error tab behaviour is documented in `connect/docs/user/ai-agents.md`.
