---
id: J04
title: 403 Forbidden on Telnyx SIP
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_telnyx/docs/admin/telnyx-setup.md]
---

## Post

Your Telnyx credential is registered. Your number routes. And every attempt to ring that phone comes back **403 Forbidden**. 🔒

The reason is a single switch on the credential connection: **SIP URI calling**. Odoo rings a phone at `sip:<credential>@sip.telnyx.com`, and while that setting is off, Telnyx answers such a call with 403 — full stop.

Oduist Connect creates the connection with **SIP URI calling = internal** for exactly this reason. If you're seeing 403s, you're almost certainly on a connection that was created by hand in Mission Control.

One more trap: don't ring the credential at the SIP subdomain. The subdomain is the inbound side only — a call there hands itself back to the routing application instead of reaching the phone.

Which SIP setting cost you the most hours? 👇

#Odoo #Telnyx #SIP

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Telnyx",
  "headline": "403 Forbidden on a",
  "headline_grad": "perfectly good phone.",
  "lede": "Odoo dials `sip:<credential>@sip.telnyx.com`. Telnyx refuses that call while *SIP URI calling* is off on the credential connection.",
  "nodes": [
    {"t": "Odoo", "s": "dials sip:<credential>@sip.telnyx.com", "c": "app"},
    {"t": "Credential connection", "s": "SIP URI calling = internal", "c": "provider"}
  ],
  "link_label": "403 while off",
  "footer": "Connect creates the connection with the setting already on"
}
```

## Notes

From the *Voice Routing* step 1 of the Telnyx setup doc. The subdomain caveat
(inbound only, calls loop back to the routing app) is worth keeping in replies.
