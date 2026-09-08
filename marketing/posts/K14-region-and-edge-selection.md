---
id: K14
title: Region and edge — latency vs data residency
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_twilio/docs/configuration.md, connect_twilio/docs/users-and-sip.md]
---

## Post

Latency and data residency are two different settings. People change one and expect the other to follow. 🌍

In the Twilio integration of Oduist Connect they're deliberately separate:

🏛️ **Region** — the data centre: US East (`us1`), Ireland (`ie1`) or Australia (`au1`). This is the residency decision, and it's the one your legal team cares about
📡 **Edge** — the network entry point closest to your users: ashburn, umatilla, dublin, frankfurt, sydney, sao-paulo, tokyo, singapore. This is the latency decision
🔗 Change the Region and the Edge resets to a sensible default (`us1 → ashburn`, `ie1 → dublin`, `au1 → sydney`) — then override it if you know better
👤 Edge is also **per user**: a Berlin team on frankfurt and a Singapore team on singapore, on the same account and the same Odoo

An EU company with an APAC support desk doesn't have to pick one compromise for everyone.

Which do you optimise first — residency or round-trip? 👇

#Odoo #Twilio #VoIP #Latency #DataResidency

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Twilio",
  "headline": "Region is the law.",
  "headline_grad": "Edge is the latency.",
  "lede": "Two settings, two questions. *Region picks the data centre; edge picks the on-ramp* — and edge is per user.",
  "tiles": [
    {"sym": "us1", "nm": "US East", "c": "provider"},
    {"sym": "ie1", "nm": "Ireland", "c": "provider"},
    {"sym": "au1", "nm": "Australia", "c": "provider"},
    {"sym": "fra", "nm": "Frankfurt edge", "c": "cyan"},
    {"sym": "sin", "nm": "Singapore edge", "c": "cyan"},
    {"sym": "tyo", "nm": "Tokyo edge", "c": "cyan"}
  ],
  "footer": "Change region → edge resets to its default → override per user on the web phone"
}
```

## Notes

Region/edge options are Twilio's own list as documented in the module. Re-check
against the Twilio console before publishing in case Twilio adds a region.
