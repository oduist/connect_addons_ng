---
id: C04
title: How to set up Telnyx with Odoo
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_telnyx/docs/admin/telnyx-setup.md]
---

## Post

The Telnyx setup step nobody warns you about isn't the API key. It's the outbound voice profile. 🌍

A fresh Telnyx profile allows **US and CA only**. Dial anywhere else and Telnyx rejects the call before it ever reaches Odoo — so a perfectly registered phone simply refuses to ring, with no webhook and no CDR to debug.

**Oduist Connect** puts that list on the settings form:

🔑 API key + the account public key — every webhook is Ed25519-verified
🌐 **Outbound Destinations**: comma-separated ISO country codes, written straight onto the profile. The sync warns you when one of your own numbers' countries is missing
🔄 **SYNC TELNYX ACCOUNT** creates the TeXML apps, SIP domains, numbers, caller IDs and the messaging profile
📱 Per-user SIP credentials issued by Telnyx for hardphones; the browser phone authenticates with a short-lived token
🤖 AI assistants are built in Odoo, not Mission Control — personal or company receptionist, with warm transfer to a phone that's actually registered

Which provider gotcha cost you the most hours? 👇

#Telnyx #Odoo #VoiceAI #Telephony #CPaaS

## Card

```json
{
  "template": "thesis",
  "accent": "purple",
  "kicker": "Oduist Connect · Telnyx",
  "headline": "Telnyx in Odoo.",
  "headline_grad": "TeXML, SIP and AI.",
  "lede": "Voice, messaging and AI receptionists on one account — *configured in Odoo, pushed to Telnyx by one sync button*.",
  "tiles": [
    {"sym": "TX", "nm": "TeXML flows", "c": "provider"},
    {"sym": "SIP", "nm": "Domains", "c": "cyan"},
    {"sym": "AI", "nm": "Assistant", "c": "purple", "hero": true},
    {"sym": "SMS", "nm": "Messaging", "c": "app"},
    {"sym": "WA", "nm": "WhatsApp", "c": "app"},
    {"sym": "RCS", "nm": "Rich chat", "c": "memory"}
  ],
  "footer": "Ed25519-verified webhooks · per-user SIP credentials · WebRTC phone"
}
```

## Notes

Known v1 limits worth having ready for replies: no WhatsApp voice calling, no
attended transfer from the web phone, call-cost fetching lags behind call
completion.
