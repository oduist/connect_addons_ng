---
id: B8
title: Vonage NCCO vs TwiML — programmable calls in JSON
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_vonage/docs/admin/vonage-setup.md, connect_twilio/docs/index.md]
---

## Post

You already know TwiML. So what actually changes when the call control is JSON instead of XML? 🧩

`connect_vonage` gives you the same shape as Twilio, in NCCO: a number's destination is a user, a call flow (IVR), or an **NCCO application** you write as static JSON, a Jinja2-templated JSON, Python, or a `model.method`. Twilio's TwiML apps give you raw markup, Python or a model method — the same escape hatches, one notation down.

What the sync does for you: creates a Vonage application with voice, messages and RTC capabilities, signed callbacks on, all webhook URLs pointed at your Odoo; creates a Vonage user per Connect user; imports numbers and seeds outgoing caller IDs. The browser phone logs into the Vonage Client SDK with a JWT minted by Odoo.

Where NCCO is genuinely narrower today: ring groups ring **sequentially**, because NCCO `connect` takes a single endpoint. Call transfer, simultaneous ring and WhatsApp/MMS sending are not there yet.

Recordings need JWT auth, so Odoo downloads them and transcribes locally.

XML or JSON — does the format actually matter to you? 👇

#Odoo #Vonage #Twilio #VoIP #CPaaS

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · Vonage",
  "headline": "Same call control.",
  "headline_grad": "JSON instead of XML.",
  "lede": "NCCO apps as static JSON, Jinja2, Python or a model method — *the same escape hatches you already use for TwiML*.",
  "columns": ["TwiML", "NCCO"],
  "rows": [
    {"f": "IVR call flows in Odoo", "m": ["✓", "✓"]},
    {"f": "Custom apps: raw / Jinja / Python", "m": ["✓", "✓"]},
    {"f": "Browser web phone", "m": ["✓", "✓"]},
    {"f": "SMS", "m": ["✓", "✓"]},
    {"f": "Simultaneous ring groups", "m": ["✓", "—"]},
    {"f": "Call transfer", "m": ["✓", "—"]},
    {"f": "WhatsApp", "m": ["✓", "—"]}
  ],
  "footer": "Signed callbacks · recordings downloaded and transcribed in Odoo"
}
```

## Notes

Vonage returns the application private key only at creation — worth flagging if
an admin asks about reusing an existing application. The card's "—" column is
the documented v1 gap list, not a permanent product statement.
