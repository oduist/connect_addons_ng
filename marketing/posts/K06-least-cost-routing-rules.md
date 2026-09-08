---
id: K06
title: Least-cost routing with regex and priorities
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch/docs/admin/freeswitch-setup.md]
---

## Post

"Least-cost routing" sounds like a product tier. In Oduist Connect it's five fields on a form. 💸

An **Outgoing Route** in the FreeSWITCH module is:

🎯 **Pattern** — a regex against the dialled number (`^\+\d{7,}$` for international, `^0\d{9}$` for national, `^(112|911)$` for emergency)
🛣️ **Gateway** — which trunk carries the matched call
🔢 **Priority** — evaluation order, lower first
✂️ **Strip** — leading digits to remove before handing the number to the carrier
➕ **Prefix** — digits to prepend after stripping (that's how `0123456789` becomes `+380123456789`)

Routes are evaluated in priority order and **the first match wins** — so put your specific patterns above the catch-all, not below it.

Two gateways from two carriers, a handful of patterns, and cheap destinations go out the cheap trunk. No separate LCR engine, no vendor lock: your trunks stay yours.

What's your routing table look like — one catch-all, or a real matrix? 👇

#Odoo #FreeSWITCH #SIP #LeastCostRouting #Telecom

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · FreeSWITCH",
  "headline": "Least-cost routing",
  "headline_grad": "is five fields.",
  "lede": "Outgoing routes are regex + gateway + priority + strip + prefix. *First match wins*, so order matters.",
  "columns": ["Strip", "Prefix"],
  "rows": [
    {"f": "International  ^\\+\\d{7,}$", "m": ["0", "—"]},
    {"f": "National  ^0\\d{9}$", "m": ["1", "+380"]},
    {"f": "Emergency  ^(112|911)$", "m": ["0", "—"]},
    {"f": "Priority decides evaluation order", "m": ["low", "first"]},
    {"f": "Gateway decides which trunk pays", "m": ["per", "route"]},
    {"f": "No match", "m": ["call", "fails"]}
  ],
  "footer": "Bring your own carriers · patterns and trunks both live in Odoo"
}
```

## Notes

The `+380` example is Ukrainian national dialling, copied from the docs. Swap the
country code if the post is repurposed for a regional audience.
