---
id: C08
title: How to connect Vonage to Odoo
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_vonage/docs/admin/vonage-setup.md]
---

## Post

Most Vonage integration guides open with: create an application, enable three capabilities, paste six webhook URLs, download the private key before the dialog closes forever. 🖲️

In **Oduist Connect** that is one button.

🧾 Fill in API key, API secret and the signature secret, then press **SYNC VONAGE ACCOUNT**
🏗️ It creates the Vonage application with voice, messages and RTC capabilities, signed callbacks enabled, and every webhook URL already pointing at your Odoo
👥 A Vonage user for each Connect user, your numbers imported and linked to the application, outgoing caller IDs seeded
🔑 The application private key is stored automatically — Vonage returns it only once, at creation, and losing it means starting over
☎️ Browser phone via the Vonage Client SDK; each number routes to a user, a call flow, or your own NCCO (static JSON, Jinja2, or a Python method)

Changed domain later? Fix the API URL and run the sync again — the webhooks re-point themselves.

Honest about today's limits: ring groups ring sequentially, and WhatsApp sending and call transfer aren't there yet.

Which provider's onboarding has burned you? 👇

#Vonage #Odoo #CPaaS #VoIP #Nexmo

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Vonage",
  "headline": "Vonage setup.",
  "headline_grad": "One sync button.",
  "lede": "The application, its capabilities, the users, the numbers and every webhook URL — *created for you*, private key stored automatically.",
  "tiles": [
    {"sym": "APP", "nm": "Application", "c": "provider", "hero": true},
    {"sym": "RTC", "nm": "Web phone", "c": "cyan"},
    {"sym": "NUM", "nm": "Numbers", "c": "app"},
    {"sym": "CID", "nm": "Caller IDs", "c": "memory"},
    {"sym": "HK", "nm": "Webhooks", "c": "magenta"},
    {"sym": "KEY", "nm": "Private key", "c": "core"}
  ],
  "footer": "NCCO call flows · signed callbacks · recordings with AI transcription"
}
```

## Notes

Prerequisites for replies: `pip install vonage` in the Odoo environment, and a
public HTTPS Odoo URL (signed-callback JWTs require it).
