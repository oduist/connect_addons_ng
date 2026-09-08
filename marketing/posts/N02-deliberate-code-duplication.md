---
id: N02
title: Why we deliberately duplicate provider code
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [specs/decisions/031-provider-model-separation.md, specs/architecture.md, AGENTS.md]
---

## Post

We considered a mixin. We rejected it. Now the same extension logic exists as four full copies across four provider modules — on purpose. 🔁

The honest version of that decision (ADR-031):

📋 **What's duplicated:** the extension destination-Reference mechanics, the E.164 / is-default caller-ID rules, the BCP-47 language list for call flows — copied in the Twilio, FreeSWITCH, Telnyx and Infobip modules
💸 **What it costs:** a fix in one copy must land in the others *in the same commit*. That rule lives in AGENTS.md because reviewers will forget it otherwise. It is real, recurring tax
🧱 **What it buys:** each provider module is installable alone, with no shared base class in core to break. Core stays technology-agnostic — a mixin would have dragged PBX concepts back into a module that is supposed to hold none
🧭 **Why the pressure exists at all:** these models only *look* alike. A FreeSWITCH extension and a Twilio extension share a shape, not a domain

DRY optimises for one codebase. We optimised for module independence, and we pay for it in diffs.

Tell me why this is wrong — where's the mixin that wouldn't leak? 👇

#Odoo #SoftwareArchitecture #Python #DRY #TechnicalDebt

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · ADR-031",
  "headline": "We chose duplication",
  "headline_grad": "over a shared mixin.",
  "lede": "Not because DRY is wrong — because the models only look alike. *Here is what the choice actually costs.*",
  "columns": ["Mixin", "Copies"],
  "rows": [
    {"f": "Fix applied once", "m": ["✓", "—"]},
    {"f": "Provider installable alone", "m": ["—", "✓"]},
    {"f": "Core stays PBX-free", "m": ["—", "✓"]},
    {"f": "Provider can diverge freely", "m": ["—", "✓"]},
    {"f": "Risk of a forgotten copy", "m": ["—", "✗"]},
    {"f": "Coupling between providers", "m": ["✗", "—"]}
  ],
  "footer": "Documented in AGENTS.md: change one copy, change them all, same commit"
}
```

## Notes

Deliberately contrarian; the cost (forgotten copies) is stated in the post and
in the card, not hidden. Do not soften it in replies — the discussion is the point.
