---
id: J17
title: Vonage private key is shown only once
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_vonage/docs/admin/vonage-setup.md]
---

## Post

Vonage returns an application's **private key only when the application is created**. Once. There is no "show it again". 🔑

Which is a problem, because that key signs the JWTs behind every webhook callback and every web-phone login. Lose it and you're not recovering it — you're creating a new application and re-pointing everything at it.

The good news: if you let **SYNC VONAGE ACCOUNT** create the application, Odoo stores the key automatically — along with the application ID, the voice/messages/RTC capabilities, `signed_callbacks`, and every webhook URL pointed at your instance.

Doing it the other way round — reusing an application you already made in the dashboard — is where people get stuck: fill in its ID **and paste its private key manually before syncing**. Same rule for the API secret.

Which credential have you had to rotate because it was shown once? 👇

#Odoo #Vonage #API

## Card

```json
{
  "template": "dialog",
  "kicker": "Oduist Connect · Vonage",
  "headline": "Shown once.",
  "headline_grad": "Never again.",
  "lede": "The application private key exists exactly at creation time. Let the sync create the app and Odoo *stores it for you*.",
  "bubbles": [
    {"side": "left", "who": "Vonage", "text": "Application created. Private key returned — this is the only time you will see it."},
    {"side": "right", "who": "SYNC VONAGE ACCOUNT", "text": "Application ID and private key stored · voice, messages and RTC capabilities · signed callbacks on · webhook URLs pointed at your Odoo"}
  ],
  "badge": "✓ Reusing an existing app? Paste its key manually before syncing",
  "footer": "Same rule for the API secret — shown only at creation"
}
```

## Notes

The Vonage module needs the `vonage` Python package installed in the Odoo
environment and a public HTTPS `connect.api_url` — both are common first-run
blockers worth mentioning in replies.
