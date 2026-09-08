---
id: M06
title: Source-available telephony
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/admin/licensing.md]
---

## Post

Ask a telephony vendor for the source of the thing that will handle every customer conversation you have. Watch what happens. 🔍

Ours is published. All of it.

Oduist Connect ships under the **Business Source License 1.1** — source-available, in a public repository:

👀 Anyone can inspect, download and install it. There is no obfuscated blob handling your calls and messages
🔧 You may read and modify the source, and have your partner or a freelancer adapt it for your own instance
🧪 Evaluation, development and staging use is free
🏭 Production use is what's licensed: a 30-day trial per module, then a commercial licence per instance
🔓 And every released version carries a **Change Date** — on it, that version becomes available under the **GNU LGPL-3.0-or-later**

That last point is the one that matters for risk reviews. Your security team can audit the code today, and the version you deployed has a published date on which its restrictions end.

Being able to read the code isn't a nice-to-have when it's the system your customers reach you through.

Does your review process require source access for critical vendors? 👇

#Odoo #OpenSource #BSL #Telephony #SecurityReview

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Source-available",
  "headline": "No black box",
  "headline_grad": "on your phone lines.",
  "lede": "Published source under BSL 1.1: read it, modify it for your instance, audit it — and *every version turns LGPL-3.0-or-later on its Change Date*.",
  "tiles": [
    {"sym": "👀", "nm": "Public source", "c": "cyan"},
    {"sym": "🔧", "nm": "Modify for you", "c": "app"},
    {"sym": "🧪", "nm": "Free non-prod", "c": "app"},
    {"sym": "🏭", "nm": "Licensed in prod", "c": "provider"},
    {"sym": "🔓", "nm": "LGPL on Change Date", "c": "magenta", "hero": true},
    {"sym": "📄", "nm": "LICENSE per module", "c": "memory"}
  ],
  "footer": "Business Source License 1.1 · each module ships its own LICENSE file"
}
```

## Notes

"Source-available", never "open source", for the current versions — the LGPL
transition happens per version on its Change Date. Not legal advice; the LICENSE
file is the binding text.
