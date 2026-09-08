---
id: H09
title: Different providers for voice and messaging, per user
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/messages.md, connect/docs/admin/core-setup.md, connect_bird/docs/admin/bird-setup.md]
---

## Post

Best voice rates and best SMS rates almost never come from the same carrier. Most integrations make you pick one anyway. 🎛️

Oduist Connect doesn't. Two independent settings on each Connect user:

☎️ **Click-to-call Provider** — which installed telephony module originates that user's calls
💬 **Messaging Provider** — which module sends that user's SMS and WhatsApp
🧑‍🤝‍🧑 Both are *per user*, so your EU team and your US team can sit on different carriers in one database
📚 Whatever the mix, calls land in one call ledger and messages in one message ledger
🔌 Leave them empty when only one provider module is installed — nothing to configure

Under the hood it's a dispatcher: each provider module claims the calls and messages tagged for it and passes the rest along. That's what makes running several carriers side by side normal rather than a hack.

Are you splitting voice and messaging across carriers today — or paying for the convenience of one? 👇

#Odoo #VoIP #SMS #Telephony #Twilio

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · Provider Routing",
  "headline": "Voice on one carrier.",
  "headline_grad": "Texts on another.",
  "lede": "Click-to-call provider and messaging provider are *set per user* — mix carriers in one database, keep one shared history.",
  "columns": ["Voice", "Messaging"],
  "rows": [
    {"f": "Twilio", "m": ["✓", "✓"]},
    {"f": "Telnyx", "m": ["✓", "✓"]},
    {"f": "Infobip", "m": ["✓", "✓"]},
    {"f": "Bird", "m": ["✓", "✓"]},
    {"f": "FreeSWITCH", "m": ["✓", "—"]},
    {"f": "Asterisk", "m": ["✓", "—"]},
    {"f": "3CX", "m": ["✓", "—"]}
  ],
  "footer": "Per-user settings · one call ledger and one message ledger regardless of mix"
}
```

## Notes

LiveKit and Dograh are voice-only too but were left out to keep the table at
seven rows. Bird messaging is outbound-only until the platform ships inbound
webhooks (see H11).
