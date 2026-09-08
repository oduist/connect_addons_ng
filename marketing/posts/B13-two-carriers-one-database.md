---
id: B13
title: Running two carriers in one Odoo database
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_twilio/docs/installation.md, specs/architecture.md, connect/docs/user/messages.md, connect_3cx/docs/admin/3cx-setup.md]
---

## Post

Sales runs on Twilio. Support sits behind the FreeSWITCH box in the server room. Same Odoo, same call list. 🔀

That is not a workaround in **Oduist Connect** — it is how the platform is built:

🎚️ **Click-to-call provider** is a field on the PBX user (`originate_provider`). Core dispatches the call to the module that owns that key; the others fall through.
💬 **Messaging provider** is a second field on the same user, with the same dispatcher pattern for SMS and WhatsApp.
🧱 **Numbering plans stay separate.** Twilio extensions and FreeSWITCH extensions are different models; there is no call path between providers, by design.
📇 **The ledger stays shared.** Calls, channels, recordings and messages are core models every provider writes into.

One detail to plan for: with several providers installed, the web phone is no longer enabled by default — you turn it on per user.

Migrating carriers becomes a per-user flag instead of a cutover weekend.

Two carriers, one database — would that solve a problem you have? 👇

#Odoo #VoIP #Telephony #Migration #CTI

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Multi-provider",
  "headline": "Two carriers.",
  "headline_grad": "One call history.",
  "lede": "The click-to-call and messaging provider are *per-user fields*. Core dispatches; provider modules chain through super().",
  "nodes": [
    {"t": "Sales team", "s": "originate_provider = twilio", "c": "provider"},
    {"t": "One Odoo database", "s": "shared calls · recordings · messages", "c": "core"},
    {"t": "Support team", "s": "originate_provider = freeswitch", "c": "app"}
  ],
  "link_label": "dispatcher",
  "footer": "Separate numbering plans · one shared ledger"
}
```

## Notes

Same pattern applies to 3CX, Bird, Telnyx, Infobip, Vonage and LiveKit — each
documents "set the user's Click-to-call Provider when several telephony modules
are installed". Twilio's `username`/`domain` constraint only fires when Twilio
SIP or the web phone is enabled, which is what makes co-installation clean.
