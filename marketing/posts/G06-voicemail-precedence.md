---
id: G6
title: Voicemail precedence rules
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/callflows.md, connect/docs/user/calls.md]
---

## Post

"Why did my personal greeting play when they called the main number?" — the classic voicemail bug report. 🎙️

It's almost always a precedence question, so **Oduist Connect** makes the order explicit:

📋 **Inside a call flow, the call flow's voicemail wins.** Its greeting, its recording — not the individual user's
👤 **A direct call to a user keeps that user's voicemail behaviour.** Personal greeting, as expected
🎯 Three call-flow paths reach it: a standalone flow with no choices or ring users, a ring group nobody answered, or an IVR the caller never responded to
🚫 Invalid keypad input does **not** jump to voicemail — it plays your invalid-input message and retries
🔑 No voicemail prompt set means no call-flow voicemail. The prompt is the switch

And on FreeSWITCH, an FS Queue keeps its own voicemail on the queue's timeout settings — separate on purpose.

Predictable beats clever when a customer is recording a message.

Ever debugged a phone tree that answered in the wrong voice? 👇

#Odoo #Voicemail #IVR #Telephony #VoIP

## Card

```json
{
  "template": "dialog",
  "kicker": "Oduist Connect · Voicemail",
  "headline": "Whose greeting",
  "headline_grad": "does the caller hear?",
  "lede": "Inside a call flow, the *call flow's* voicemail wins. Dial a user directly and you get theirs.",
  "bubbles": [
    {"side": "left", "who": "Caller · main line", "text": "\"...nobody in the ring group picked up.\""},
    {"side": "right", "who": "Call flow", "text": "\"You've reached Sales. Please leave a message after the tone.\" — the flow's own greeting, not an individual's."}
  ],
  "badge": "✓ No voicemail prompt set = no call-flow voicemail",
  "footer": "Call flow > user · invalid input retries instead"
}
```

## Notes

FS Queue voicemail is configured separately on the queue timeout settings — do
not conflate it with call-flow voicemail in replies.
