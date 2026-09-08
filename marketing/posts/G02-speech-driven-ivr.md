---
id: G2
title: Speech-driven IVR
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/callflows.md, connect_twilio/docs/call-flows-twiml.md]
---

## Post

"Press 1 for Sales." — the caller is driving, holding the phone to their ear, and has no idea what 2 and 3 were. 🚗

Let them just say it.

**Oduist Connect** call flows accept three input types:

⌨️ **DTMF** — the classic keypad digit
🗣️ **Speech** — the caller says a keyword: "sales", "support"
🎯 **Both** — whichever the caller reaches for first

Each menu choice carries its digits *and* an optional speech hint, so "sales" and "1" land on the same extension. On Twilio the flow renders as a TwiML `<Gather>`; the spoken result is POSTed back and matched against your choices. Say something the menu doesn't know, and the invalid-input message plays and the prompt repeats.

Configured in an Odoo form. No speech pipeline to host.

Would your callers rather press or speak? 👇

#Odoo #IVR #SpeechRecognition #Twilio #Telephony

## Card

```json
{
  "template": "dialog",
  "kicker": "Oduist Connect · Call Flows",
  "headline": "Let callers say it.",
  "headline_grad": "Not press it.",
  "lede": "Every IVR choice takes digits *and* a speech hint — accept DTMF, speech, or both on the same menu.",
  "bubbles": [
    {"side": "left", "who": "IVR", "text": "\"Thank you for calling. Press 1 for Sales, 2 for Support — or just tell me what you need.\""},
    {"side": "right", "who": "Caller", "text": "\"Sales.\""}
  ],
  "badge": "✓ Routed to the Sales extension",
  "footer": "DTMF · Speech · Both — one call flow, one form"
}
```

## Notes

Twilio implementation detail (`<Gather>` + `/twilio/webhook/callflow/<id>/gather`)
is from the Twilio module doc; other providers implement the same input types
differently — keep the post provider-neutral in replies.
