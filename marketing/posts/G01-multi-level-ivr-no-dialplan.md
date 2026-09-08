---
id: G1
title: Multi-level IVR without a dialplan
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/callflows.md]
---

## Post

The last time you changed a phone menu, did you open a text editor on a server? 🖥️

In **Oduist Connect** an IVR is an Odoo record. You fill a form, and callers hear the new menu.

🌳 A call flow plays a prompt and collects a choice — DTMF, speech, or both
🔢 Each choice points at an extension: a user, a queue, or another call flow
🪜 Point a choice at another call flow and you have a second level. Chain as deep as you need
🔁 Invalid input plays your error message and repeats the prompt — the caller isn't dumped
📞 Turn Gather Input off and the same flow becomes a ring group: one greeting, then everyone's phone rings

No dialplan syntax, no reload window, no ticket to your integrator. The people who own the phone tree can finally edit it.

How many levels deep does your phone menu go — and who is allowed to change it? 👇

#Odoo #IVR #Telephony #VoIP #CallCenter

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Call Flows",
  "headline": "An IVR is a form.",
  "headline_grad": "Not a dialplan.",
  "lede": "Prompt, choices, destinations — edited in Odoo. *Chain call flows* to build menus as deep as you need.",
  "nodes": [
    {"t": "Caller", "s": "dials your number", "c": "provider"},
    {"t": "Call Flow", "s": "prompt · DTMF or speech", "c": "cyan"},
    {"t": "User · Queue · Sub-menu", "s": "routed by the choice", "c": "app"}
  ],
  "link_label": "routes to",
  "footer": "Twilio · Telnyx · FreeSWITCH · Infobip — same call flow model"
}
```

## Notes

Ring-group behaviour with Gather Input disabled: the Prompt Message is played
once as a greeting, no input collected (callflows.md).
