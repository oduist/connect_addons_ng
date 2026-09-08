---
id: C01
title: How to connect Twilio to Odoo
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_twilio/docs/installation.md, connect_twilio/docs/configuration.md]
---

## Post

The entire Twilio setup is a pip install, four credentials and one button. Most teams are taking calls in Odoo before lunch. ⏱️

Here's the whole thing:

📦 `pip install twilio`, then install **Oduist Connect Twilio** from Apps
🌐 Set your public HTTPS Odoo URL first — every webhook Connect pushes to Twilio is built from it
🔑 Paste four values from the Twilio Console: Account SID, Auth Token, API Key SID, API Key Secret
🔄 Press **SYNC TWILIO ACCOUNT** — TwiML apps, SIP domains, numbers, outgoing caller IDs, WhatsApp senders and content templates are all imported for you
☎️ The browser phone shows up in the systray; incoming webhooks are signature-verified out of the box

No SIP trunk to order, no PBX to rack. And nothing here locks you in: the same call ledger runs on Telnyx, Asterisk or self-hosted FreeSWITCH later, with your history intact.

What's stopping you from putting your calls in Odoo today? 👇

#Odoo #Twilio #VoIP #CTI

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Twilio",
  "headline": "Twilio in Odoo.",
  "headline_grad": "Four fields, one sync.",
  "lede": "Install the module, paste four credentials, press *Sync* — numbers, caller IDs and WhatsApp senders import themselves.",
  "nodes": [
    {"t": "Twilio", "s": "voice · SMS · WhatsApp", "c": "provider"},
    {"t": "Odoo", "s": "CRM · Helpdesk · Contacts", "c": "app"}
  ],
  "link_label": "Connect",
  "footer": "Web phone · IVR call flows · recordings · AI transcripts & summaries"
}
```

## Notes

Twilio is a licensed Oduist module — a 30-day production trial starts on
install. Worth mentioning in replies if pricing comes up.
