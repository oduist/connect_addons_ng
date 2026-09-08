---
id: B01
title: Odoo 19 Phone vs Oduist Connect
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources:
  - https://www.odoo.com/documentation/19.0/applications/productivity/phone.html
  - https://oduist.com/blog/odoo-experience-2025-ai-summaries-2/019-what-s-new-in-voip-23
  - connect_twilio/docs/index.md
  - connect/docs/user/callflows.md
  - connect_asterisk/docs/admin/asterisk-setup.md
---

## Post

Odoo 19 shipped call recording and AI transcripts in the Phone app. That's genuinely good — and it makes half of every "Odoo VoIP is just a dialer" slide obsolete, including one of ours. 🙂

So let me redraw the line honestly.

What Odoo 19 Phone now does well: a redesigned browser softphone, recording you can start and stop mid-call, OpenAI transcripts and summaries on the call record, attended transfers.

Where **Oduist Connect** still goes further:

🔌 Your existing PBX keeps running — Asterisk, FreePBX or 3CX
☎️ Desk phones and classic SIP — Odoo Phone needs SIP over WebSocket
🌳 IVR, ring groups and queues, built in Odoo forms
🤖 AI voice agents that answer the phone, open tickets and take orders
🌍 Nine providers instead of three, self-hosted included

If recording and transcripts are all you need, use Odoo's. Really — it's built in and it works.

If your phone system has to survive contact with a real PBX, that's where we start.

Which of these do you actually need? 👇

#Odoo #Odoo19 #VoIP #Telephony

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · Odoo 19",
  "headline": "Odoo 19 Phone got good.",
  "headline_grad": "Here's what's left.",
  "lede": "Recording and AI summaries ship with Odoo now. *The gap moved* — to providers, desk phones, IVR and agents that answer.",
  "columns": ["Odoo 19 Phone", "Connect"],
  "rows": [
    {"f": "Browser softphone & click-to-call", "m": ["✓", "✓"]},
    {"f": "Call recording", "m": ["✓", "✓"]},
    {"f": "AI transcript & summary", "m": ["✓", "✓"]},
    {"f": "Keep your existing PBX", "m": ["—", "✓"]},
    {"f": "Desk phones & classic SIP", "m": ["—", "✓"]},
    {"f": "IVR, queues & call flows", "m": ["—", "✓"]},
    {"f": "AI agents that answer calls", "m": ["—", "✓"]}
  ],
  "footer": "Odoo 19 Phone: 3 providers · Connect: 9, plus the PBX you already run"
}
```

## Notes

**This post was corrected after the first draft got it wrong.** The original
claimed Odoo's built-in module has no recording and no transcription. That was
true of earlier releases and is false for Odoo 19, where VoIP was renamed
**Phone** and gained admin-configurable call recording (start/stop mid-call),
OpenAI transcription with an auto summary stored on the call, and attended
transfers.

Verified 2026-09 against the Odoo 19 Phone documentation and our own blog write-up
(both listed in `sources`). Re-verify before publishing: Odoo ships fast and the
concession rows are the ones that make the rest of the card credible.

Two claims to keep precise in the comments:

- **Provider count.** Odoo Phone documents Axivox, OnSIP and DIDWW, plus custom
  providers that speak SIP over WebSocket. The "classic SIP-only endpoints won't
  work in the browser" limitation is what the desk-phone row rests on.
- **IVR and queues.** Odoo Phone itself does not build them; with Axivox you
  configure dial plans in Axivox's own console. Say "built in Odoo forms" — do
  not say "Odoo has no IVR at all", because an Axivox customer will correct you.

Naming: Odoo 19 calls it **Phone**, but people still search "Odoo VoIP". Use both
terms across the article version of this post.
