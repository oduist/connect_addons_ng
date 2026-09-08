---
id: G14
title: After-hours routing
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch_website/docs/admin/working-schedule.md, connect/docs/user/callflows.md]
---

## Post

18:04. A customer calls. Ring… ring… ring… ring. Nobody is going to answer, and nothing is going to tell them that. 🔇

Silence is the worst after-hours policy, and it's usually the default one.

Turn on **Use Working Schedule** on a number in **Oduist Connect** and the number gets a second personality:

🕘 The normal destination fields become the route **during** working hours
🌙 The **After-hours Routing** group takes over outside them — send the call to a user, a call flow, or a queue
📢 Public holidays can carry their own **Prompt Message**, spoken to the caller in the number's **Prompt Language**
🎛️ Route to a call flow after hours and you get a full menu: "leave a message", "emergency line", "call back tomorrow from 08:00"
⚠️ With no after-hours destination configured, the caller hears the holiday prompt (if set) and the call is hung up — deliberately, not by accident

Even "we're closed, we open at 8" beats twelve rings into nothing.

What does your main line do at 21:00 tonight? 👇

#Odoo #Telephony #FreeSWITCH #CustomerService #VoIP

## Card

```json
{
  "template": "dialog",
  "kicker": "Oduist Connect · After Hours",
  "headline": "Closed is a route.",
  "headline_grad": "Not a silence.",
  "lede": "One number, two destinations: *working hours* and *after-hours* — user, call flow or queue, plus a holiday prompt.",
  "bubbles": [
    {"side": "left", "who": "Caller · 18:04", "text": "(dials the main line — the schedule says closed)"},
    {"side": "right", "who": "After-hours flow", "text": "\"Thanks for calling. We're closed and open again tomorrow at 08:00. Press 1 to leave a message.\""}
  ],
  "badge": "✓ Holiday prompt spoken in the number's Prompt Language",
  "footer": "Use Working Schedule on any FreeSWITCH number"
}
```

## Notes

Prompt Language selects the Piper TTS voice for holiday prompts. If the
`dialplan_inbound_did` template was customized, it must be reset or merged with
the `schedule_prompt` block for the prompt to play.
