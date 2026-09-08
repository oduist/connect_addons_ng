---
id: G7
title: Jinja2 voicemail greetings per user
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/admin/core-setup.md, connect_freeswitch/docs/admin/freeswitch-setup.md]
---

## Post

Forty employees. Forty voicemail greetings to record, and one of them will still say the name of someone who left in 2023. 🎧

**Oduist Connect** treats the greeting as a template, not a recording. Every PBX user ships with:

```
Hello, this is {{user.name}}. I'm unable to take your
call right now. Please leave a message after the tone.
```

🧩 It's a Jinja2 template with the user record in scope — write it once, it renders per person
🗣️ Spoken by TTS, so nobody books a quiet room to record anything
🌍 Each user has their own **Language** field: the same template is read in the voice of their locale
📞 A separate **Greeting Message** can be spoken to the caller *before* the user's phone even rings
✏️ Any user can still override their own text without touching the default

New hire on Monday? Their voicemail is correct on Monday.

How many outdated greetings do you think are live in your company right now? 👇

#Odoo #Voicemail #Telephony #TTS #ITAdmin

## Card

```json
{
  "template": "dialog",
  "kicker": "Oduist Connect · PBX Users",
  "headline": "One template.",
  "headline_grad": "Every greeting correct.",
  "lede": "A Jinja2 voicemail prompt with `{{user.name}}` in scope — *rendered per user, spoken in their language*.",
  "bubbles": [
    {"side": "right", "who": "Template", "text": "\"Hello, this is {{user.name}}. I'm unable to take your call right now. Please leave a message after the tone.\""},
    {"side": "left", "who": "Caller hears", "text": "\"Hello, this is Maria Rossi. I'm unable to take your call right now...\" — read by the Italian TTS voice."}
  ],
  "badge": "✓ New user on Monday = correct greeting on Monday",
  "footer": "Per-user Language & Voice · optional pre-ring greeting"
}
```

## Notes

The default prompt text is the literal `connect.user.voicemail_prompt` default.
Jinja2 context is `{'user': <connect.user record>}`.
