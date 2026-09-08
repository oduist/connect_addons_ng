---
id: B7
title: Infobip vs Twilio — event-driven voice, no markup language
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_infobip/docs/admin/infobip-setup.md, connect_twilio/docs/index.md]
---

## Post

Infobip has no TwiML. No TeXML. No NCCO. There is no call-control markup at all — and that changes how the integration is built. 📡

With `connect_infobip`, voice is purely **event-driven**: Infobip posts call events to Odoo over webhooks, and Odoo answers with REST actions on the live call. No document to render, no template to debug.

What that buys you in practice:
🔔 Inbound calls simply do not work until the webhooks are configured — the failure mode is loud rather than silent.
📱 Per-user WebRTC identities are generated automatically; a number can ring the web phone and an external phone by priority, with ring timeouts running on the Infobip platform.
🎙️ Recordings are downloaded into Odoo attachments and picked up by the core OpenAI transcription.
💬 SMS and WhatsApp from the same account.

Honest v1 scope: no IVR/call flows, no recorded voicemail, no RCS, no transfer from the web phone — and the browser only rings while a tab is open.

Event-driven or markup-driven: which do you prefer to debug? 👇

#Odoo #Infobip #VoIP #CPaaS #WebRTC

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Infobip",
  "headline": "No TwiML.",
  "headline_grad": "Events and REST.",
  "lede": "Infobip posts call events; Odoo answers with REST actions on the live call. *There is no markup document to render.*",
  "nodes": [
    {"t": "Infobip Calls API", "s": "CALL_RECEIVED · dialog events", "c": "provider"},
    {"t": "Odoo", "s": "decides · answers with REST actions", "c": "app"}
  ],
  "link_label": "webhooks",
  "footer": "WebRTC web phone · SMS & WhatsApp · recordings into Odoo"
}
```

## Notes

Infobip does not sign its webhooks: the URLs shown in the settings form embed a
shared token. Mention that only alongside the warning to keep those URLs out of
screenshots and logs. The v1 limitations list is the fair-comparison anchor —
do not drop it from the post.
