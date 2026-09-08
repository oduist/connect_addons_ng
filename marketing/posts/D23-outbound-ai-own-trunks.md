---
id: D23
title: Outbound AI campaigns through your own trunks
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_dograh/docs/admin/dograh-setup.md, connect_livekit/docs/admin/livekit-setup.md]
---

## Post

Most outbound AI-calling tools arrive with their own numbers and their own dialer. Very convenient — right up to the moment you notice your caller ID, your call rates and your call history now live inside someone else's product. 📞

Oduist Connect keeps outbound AI on infrastructure you already own:

🚀 Dograh campaigns and test calls originate through Odoo: Dograh asks, Odoo picks the matching outgoing route and dials it on your FreeSWITCH trunk
🆔 No caller ID supplied by the campaign? Odoo applies your default outgoing CallerID — one rule, every provider
🎛️ LiveKit agents start an outbound AI call from the record with Call with Agent, over your own BYO carrier trunk
📒 Every leg lands in Connect → Calls with its recording, exactly like a human-dialled call
🔌 Switch carrier and the campaigns keep running — the trunk is yours, not the AI vendor's

Your dialer should be a feature you rent, not a landlord you move in with.

What would you have an AI agent call about first — renewals, no-shows, overdue invoices? 👇

#Odoo #VoiceAI #Outbound #Telephony #AI

## Card

```json
{
  "template": "diagram",
  "accent": "purple",
  "kicker": "Oduist Connect · Dograh & LiveKit",
  "headline": "Outbound AI calls,",
  "headline_grad": "your own trunks.",
  "lede": "Campaigns originate *through Odoo* on your FreeSWITCH or BYO carrier trunk — with your default caller ID.",
  "nodes": [
    {"t": "AI agent", "s": "Dograh campaign · LiveKit", "c": "purple"},
    {"t": "Your trunks", "s": "FreeSWITCH · BYO carrier", "c": "provider"},
    {"t": "Odoo", "s": "call log · recordings", "c": "app"}
  ],
  "link_label": "Connect",
  "footer": "Outgoing routes · default CallerID · calls in the Odoo ledger"
}
```

## Notes

Compliance is the obvious comment-thread risk on outbound AI: consent and
do-not-call rules are the customer's responsibility, and nothing in the module
enforces them. Do not claim otherwise in replies.
