---
id: C06
title: How to connect Infobip to Odoo
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_infobip/docs/admin/infobip-setup.md]
---

## Post

Infobip has no TwiML. No NCCO. No call-control XML at all. ⚡

Voice on the Calls API is purely event-driven: the platform sends events, your app answers with REST actions. Which is exactly why the webhook step is not optional — skip it and inbound calls do nothing at all.

Connecting it to Odoo with **Oduist Connect**:

🔗 Enter your personalized base URL and API key, then press **SYNC INFOBIP ACCOUNT** — it creates the "Odoo Connect" Calls configuration and imports your numbers and outgoing caller IDs
📥 Paste the voice receive and voice event URLs into that configuration in the Infobip portal
🔐 Infobip doesn't sign webhooks, so every URL carries a secret token Odoo checks in constant time — keep those URLs out of screenshots and logs
🎧 WebRTC phone in the systray, plus SMS and WhatsApp in the same message ledger
⏺️ Recordings are pulled by a scheduled job and transcribed by the core OpenAI pipeline

Honest about v1: number → user or external number, no IVR yet.

Anyone else running Infobip voice in production? What surprised you? 👇

#Infobip #Odoo #CPaaS #WebRTC #Telephony

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Infobip",
  "headline": "No XML. No IVR file.",
  "headline_grad": "Just events.",
  "lede": "Infobip voice is event-driven — Odoo receives the call events and *drives the call with REST actions*. Set the webhooks or nothing rings.",
  "nodes": [
    {"t": "Infobip", "s": "Calls API · SMS · WhatsApp", "c": "provider"},
    {"t": "Odoo", "s": "call & message ledger", "c": "app"}
  ],
  "link_label": "webhook events",
  "footer": "WebRTC systray phone · token-authenticated webhooks · recordings + AI summaries"
}
```

## Notes

Two limits to keep ready: the browser only receives inbound calls while a tab
with the web phone is open (use the External Phone ring step as fallback), and
Infobip exposes no per-call price, so call costs aren't fetched.
