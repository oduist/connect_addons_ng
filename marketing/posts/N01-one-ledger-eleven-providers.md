---
id: N01
title: One ledger, eleven providers
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [specs/architecture.md, specs/decisions/031-provider-model-separation.md, AGENTS.md]
---

## Post

Eleven telephony and voice-AI providers in one Odoo app, and the core module does not import a single vendor SDK. That constraint is the whole design. 🧱

Two model families, one rule:

📒 **The ledger is shared.** `connect.call`, `connect.channel`, `connect.recording`, `connect.message`, `connect.user` — one call history, whatever rang. Providers `_inherit` these and add adapter fields and webhook handlers; they never redefine them
🔧 **PBX configuration is owned per provider.** `connect.twilio.number`, `connect.freeswitch.number`, `connect.telnyx.exten` — separate models, separate numbering plans. Extension 100 on FreeSWITCH has no relationship to extension 100 on Twilio, so they don't share a table
🔀 **Cross-provider calls are dispatchers.** `originate_call()` and `message.send()` resolve the provider from a per-user field, then chain through `super()`
🧩 A provider can own *zero* configuration models — the 3CX module is settings, user and channel extensions plus webhook controllers, nothing else

Co-installing several providers in one database is a supported case, not an accident.

Tell me why this is wrong — where would you have put the boundary? 👇

#Odoo #SoftwareArchitecture #VoIP #Python #OpenSource

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Architecture",
  "headline": "One shared ledger.",
  "headline_grad": "Eleven providers.",
  "lede": "Core never imports a vendor SDK. *Call history is shared; numbering plans are not* — and click-to-call is a dispatcher.",
  "tiles": [
    {"sym": "TW", "nm": "Twilio", "c": "provider"},
    {"sym": "FS", "nm": "FreeSWITCH", "c": "provider"},
    {"sym": "AST", "nm": "Asterisk", "c": "provider"},
    {"sym": "TX", "nm": "Telnyx", "c": "provider"},
    {"sym": "LK", "nm": "LiveKit", "c": "cyan"},
    {"sym": "IB", "nm": "Infobip", "c": "cyan"},
    {"sym": "BD", "nm": "Bird", "c": "cyan"},
    {"sym": "3CX", "nm": "3CX", "c": "app"},
    {"sym": "VN", "nm": "Vonage", "c": "app"}
  ],
  "footer": "Plus Dograh and ElevenLabs voice agents · ADR-031 provider model separation"
}
```

## Notes

Eleven = the nine tiles plus Dograh and ElevenLabs (voice-agent providers).
`connect_vonage` is not yet listed in AGENTS.md's module table — confirm it is
publicly announced before this post goes out, or swap the tile for Dograh.
