---
id: G18
title: Click-to-call from any phone field
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/getting-started.md, connect/docs/user/calls.md]
---

## Post

Copy the number. Alt-tab. Paste into the softphone. Realise you grabbed the fax line. 🙃

Ten seconds, forty times a day, for years.

In **Oduist Connect**, a phone number in Odoo is a button:

📱 Click any phone field — partner form, lead, call record, channel — and the widget dials it
🔍 Or search a contact by name straight from the widget's Contacts tab and call from there
🔁 **Redial** on any call record calls that number again, one click
🏢 The same control appears on Connect's own forms, so you can call back from a recording or a call log
🔀 Several providers installed? Each user has a **Click-to-call Provider** field that decides who places their calls — Twilio, Telnyx, FreeSWITCH, Asterisk, 3CX and more

And every call comes back into Odoo linked to the partner, so the click that started it is also the click that logs it.

The gap between "I should call them" and "it's ringing" should be one click. Not four.

How many clicks does your CRM need to place a call? 👇

#Odoo #CRM #ClickToCall #CTI #Telephony

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Click-to-call",
  "headline": "A phone number",
  "headline_grad": "is a button.",
  "lede": "Click a phone field anywhere in Odoo — the widget dials, and the call comes back *linked to the partner*.",
  "nodes": [
    {"t": "Any phone field", "s": "partner · lead · call · channel", "c": "app"},
    {"t": "Phone widget", "s": "dials via your provider", "c": "cyan"},
    {"t": "Call history", "s": "logged & linked to the contact", "c": "provider"}
  ],
  "link_label": "one click",
  "footer": "Per-user Click-to-call Provider · Twilio · Telnyx · FreeSWITCH · Asterisk · 3CX"
}
```

## Notes

Odoo list rows keep phone numbers as plain text; the clickable phone control is
on form views. On 3CX, click-to-call opens the 3CX Web Client dial URL rather
than a Connect softphone.
