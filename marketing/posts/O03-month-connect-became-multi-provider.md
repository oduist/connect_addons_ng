---
id: O03
title: The month Connect became multi-provider
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [docs/changelog.md, specs/architecture.md]
---

## Post

Eleven new integrations shipped in a single month. The change that made them possible wasn't any of them. 🧱

**Provider model separation.** Extensions, numbers, call flows and caller IDs are now owned by each provider instead of shared — a FreeSWITCH extension and a Twilio extension are simply different records. That one decision is why several providers can live in one Odoo database at all.

☎️ New carriers and PBXs: Telnyx, Infobip, Vonage, Bird, Asterisk / FreePBX / Issabel, 3CX V20, and self-hosted LiveKit
🤖 New AI voice agents: ElevenLabs, Dograh and Pipecat
🕐 Working schedules for inbound numbers, plus website opening-hours widgets
👤 Each user picks which provider places their calls and which one sends their messages
📜 And all modules moved to the Business Source License 1.1

The point isn't the count. It's that the shared call ledger stayed shared — so changing carrier doesn't cost you your call history.

Which of those would you actually plug into Odoo first? 👇

#Odoo #Telephony #VoIP #CPaaS #VoiceAI

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Platform",
  "headline": "Eleven integrations.",
  "headline_grad": "One call history.",
  "lede": "Providers own their own numbering plans; the *call, message and recording ledger stays shared* — so co-installing them in one database works.",
  "tiles": [
    {"sym": "TW", "nm": "Twilio", "c": "provider"},
    {"sym": "TX", "nm": "Telnyx", "c": "provider"},
    {"sym": "IB", "nm": "Infobip", "c": "provider"},
    {"sym": "VG", "nm": "Vonage", "c": "provider"},
    {"sym": "BD", "nm": "Bird", "c": "magenta"},
    {"sym": "FS", "nm": "FreeSWITCH", "c": "cyan"},
    {"sym": "AS", "nm": "Asterisk", "c": "app"},
    {"sym": "3CX", "nm": "3CX V20", "c": "app"},
    {"sym": "LK", "nm": "LiveKit", "c": "memory"}
  ],
  "footer": "Per-user click-to-call and messaging provider · one shared ledger"
}
```

## Notes

Time-sensitive: this is a retrospective of the 2026-07 changelog. Publish soon,
or reframe as evergreen by leading with the architecture ("why a telephony
platform should not share its numbering plan") and dropping "in a single month".

The eleven counted are the integrations added in that month: asterisk, telnyx,
infobip, bird, vonage, 3cx, livekit, elevenlabs, dograh, pipecat and
freeswitch_website. The card shows nine (grid limit) — Twilio is on the card
though it predates the month, so avoid implying it was new.
