---
id: H04
title: WhatsApp voice calls from Odoo, and their limits
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_twilio/docs/messaging.md, connect/docs/user/calls.md]
---

## Post

Error **37007**. That's the number you'll meet if you assume WhatsApp calling works everywhere. Let's get ahead of it. 📵

**Oduist Connect + Twilio** puts a **WhatsApp Call** action next to the ordinary Call action on any phone number:

📞 Connect rings your own web phone first over normal voice
🟢 That leg then places the WhatsApp leg to the destination, carrying your WhatsApp identity
🗂️ Both legs land in the call ledger, recorded with call type **WhatsApp**
🚫 Where Meta doesn't permit business-initiated WhatsApp calls, Twilio rejects the leg with error 37007 — *"Business-initiated calling is not available in the country"* — and it's right there on the call record's Error tab
📥 Inbound WhatsApp calls from those same countries still work fine

Nothing in Connect can lift a Meta country restriction. What we can do is show you exactly why a call failed instead of leaving you guessing.

Would inbound-only WhatsApp calling still be useful for your support line? 👇

#WhatsApp #Odoo #Twilio #VoIP #CustomerService

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · WhatsApp Calling",
  "headline": "WhatsApp calls in Odoo.",
  "headline_grad": "And one hard limit.",
  "lede": "Business-initiated WhatsApp calling is *restricted by destination country*. Inbound WhatsApp calls are not.",
  "columns": ["You call out", "They call in"],
  "rows": [
    {"f": "Works where Meta permits it", "m": ["✓", "✓"]},
    {"f": "Works in restricted countries", "m": ["—", "✓"]},
    {"f": "Lands in the call ledger", "m": ["✓", "✓"]},
    {"f": "Call type = WhatsApp", "m": ["✓", "✓"]},
    {"f": "Contact matched automatically", "m": ["✓", "✓"]},
    {"f": "Can fail with error 37007", "m": ["✓", "—"]}
  ],
  "footer": "Error 37007 is shown on the call record's Error tab · Twilio integration"
}
```

## Notes

WhatsApp voice calling is a Twilio-only capability today; Telnyx v1 explicitly
does not integrate WhatsApp voice (messaging only). Don't generalise to other
providers.
