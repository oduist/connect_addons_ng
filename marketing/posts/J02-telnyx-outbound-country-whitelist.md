---
id: J02
title: Call failed — Telnyx outbound country whitelist
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_telnyx/docs/admin/telnyx-setup.md]
---

## Post

A registered phone. A valid number. And every call dies with a bare **"Call failed"**. 🚧

Here is the part nobody reads in the Telnyx docs: a **new outbound voice profile ships allowing `US, CA` only**. Telnyx rejects a call to any other country *before* it ever reaches Odoo — no webhook, no routing, nothing to debug on your side.

The fix takes ten seconds. In **Connect → Telnyx → Configuration → Settings**, fill the **Outbound Destinations** field with comma-separated ISO codes (`PL, DE, US`). Saving writes straight onto the profile; leaving it empty allows every destination. The account sync reads the list back and warns you when one of your own numbers sits in a country that isn't on it.

Which provider default has burned you the hardest? 👇

#Odoo #Telnyx #VoIP

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · Telnyx",
  "headline": "A new profile allows",
  "headline_grad": "two countries. Two.",
  "lede": "Telnyx rejects non-whitelisted destinations *before* the call reaches Odoo. Set **Outbound Destinations** in the settings form.",
  "columns": ["Default", "Configured"],
  "rows": [
    {"f": "United States", "m": ["✓", "✓"]},
    {"f": "Canada", "m": ["✓", "✓"]},
    {"f": "Germany", "m": ["—", "✓"]},
    {"f": "Poland", "m": ["—", "✓"]},
    {"f": "United Kingdom", "m": ["—", "✓"]},
    {"f": "Australia", "m": ["—", "✓"]}
  ],
  "footer": "Connect → Telnyx → Configuration → Settings → Outbound Destinations"
}
```

## Notes

The `US, CA` default and the "rejected before it reaches Odoo" behaviour come
from the *Outbound destinations* section of the Telnyx setup doc. The country
rows on the card are illustrative — any ISO code works.
