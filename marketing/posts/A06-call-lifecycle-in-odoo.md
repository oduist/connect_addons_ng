---
id: A06
title: From ringing phone to closed deal — the call lifecycle
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/calls.md, connect/docs/user/callflows.md, connect/docs/user/recordings.md, connect/docs/user/business-records.md, connect/docs/user/getting-started.md]
---

## Post

A number rings at 10:14. By 10:31 there is a summary on the sale order and nobody typed a word. 📞

Here is every step in between, in **Oduist Connect**:

1️⃣ The call hits a number, which routes to a user, an IVR menu, a ring group, a queue — or an AI agent.
2️⃣ The caller is matched to a contact, and a notification pops with the name.
3️⃣ The bridges attach the call to the record it belongs to: lead, ticket, order, invoice, task or employee.
4️⃣ Recording runs — automatically by user or call flow, or started mid-call from the phone widget.
5️⃣ OpenAI Whisper transcribes it; the model your admin picks writes the summary.
6️⃣ The summary is posted to the contact's chatter and to the linked record's chatter.
7️⃣ Anything missing? **Create Lead**, **Create Ticket**, **Create Sale Order** or **Create Task** straight from the call — pressing twice opens the record instead of duplicating it.

Where does your call data die today? 👇

#Odoo #CRM #Telephony #AI #Sales

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Lifecycle",
  "headline": "Ring at 10:14.",
  "headline_grad": "Summary at 10:31.",
  "lede": "Route, match, record, transcribe, summarise, post to the chatter — *and none of it is anybody's job*.",
  "nodes": [
    {"t": "Incoming call", "s": "user · IVR · queue · AI agent", "c": "provider"},
    {"t": "Connect ledger", "s": "recording · transcript · summary", "c": "core"},
    {"t": "Odoo record", "s": "lead · ticket · order · invoice", "c": "app"}
  ],
  "link_label": "automatic",
  "footer": "Whisper transcription · GPT summary · chatter integration"
}
```

## Notes

Transcript and summary stay on the call even if the audio recording is later
deleted — worth mentioning if a data-retention question comes up.
