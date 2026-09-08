---
id: G10
title: Pause and resume recording mid-call
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [docs/changelog.md, connect/docs/user/recordings.md]
---

## Post

"Can you read me your card number?" 💳

That's the moment your recording policy either works or creates a liability sitting in an audio file forever.

**Oduist Connect** ships in-call recording control in the browser softphone for Twilio and FreeSWITCH — pause the recording during the call, take the sensitive part, resume.

⏸️ One button in the widget, reachable while you're talking. No transfer, no hold trick
🔴 A purple **REC** badge means nothing is being captured right now
⏹️ A purple stop icon means audio is genuinely running — and pressing it stops whichever recording is active
🎯 Auto, call-flow and manual recordings share the same control, so the agent never has to know which one started it
📼 The sensitive stretch simply never reaches storage, so it can never leak from it

Compliance people love this. So do agents, who otherwise just don't record at all.

Does your team record card and health details today — on purpose? 👇

#Odoo #CallRecording #PCIDSS #Compliance #Telephony

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Recording",
  "headline": "Pause the recording.",
  "headline_grad": "Not the call.",
  "lede": "In-call recording control in the softphone: *stop before the card number, resume after* — Twilio and FreeSWITCH.",
  "tiles": [
    {"sym": "⏺", "nm": "Recording", "c": "core"},
    {"sym": "⏸", "nm": "Card number", "c": "memory", "hero": true},
    {"sym": "⏺", "nm": "Resumed", "c": "core"},
    {"sym": "1", "nm": "Button in widget", "c": "cyan"},
    {"sym": "0", "nm": "Transfers needed", "c": "app"},
    {"sym": "∀", "nm": "Auto · flow · manual", "c": "provider"}
  ],
  "footer": "Twilio & FreeSWITCH browser softphone"
}
```

## Notes

Doc wording check: the changelog (2026-07) says "pause and resume"; the user doc
(recordings.md) describes the same control as start/stop. Worth aligning the two
before this post goes out. Do not claim the resumed audio ends up in a single
file — that is not stated anywhere and depends on the provider.
