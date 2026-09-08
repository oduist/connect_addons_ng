---
id: M02
title: BSL 1.1 explained for Odoo buyers
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/admin/licensing.md]
---

## Post

"Source-available" makes procurement teams nervous, mostly because nobody explains it. So — plainly, what the Oduist Connect licence says. 📄

All modules ship under the **Business Source License 1.1**:

📂 The source is published in a public repository — anyone can inspect, download and install it. Each module ships its own `LICENSE` file
🧪 **Non-production use is free**: evaluation, development and staging. You may read and modify the source, and have partners or freelancers adapt it for your own instance
🏭 **Production** is free for the module's 30-day trial; after that it needs a commercial licence
🔓 Each released version carries a **Change Date**. On it, that version becomes available under the **GNU LGPL-3.0-or-later** and its BSL restrictions end
📅 The Change Date is set per module and moves forward with new major versions

One thing the docs are blunt about: BSL restricts *use*, not modification. Editing out the licensing code is possible; running past the trial without a licence is still a breach.

Not legal advice — the `LICENSE` file in each module is the binding text.

Where does your procurement process put source-available licences? 👇

#Odoo #OpenSource #BSL #SoftwareLicensing #Telephony

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · BSL 1.1",
  "headline": "Source-available,",
  "headline_grad": "spelled out.",
  "lede": "Read and modify the source freely; production beyond the 30-day trial needs a licence — and *every version turns LGPL-3.0-or-later on its Change Date*.",
  "columns": ["No licence", "Licensed"],
  "rows": [
    {"f": "Read the full source", "m": ["✓", "✓"]},
    {"f": "Modify it for your instance", "m": ["✓", "✓"]},
    {"f": "Dev & staging use", "m": ["✓", "✓"]},
    {"f": "Production, first 30 days", "m": ["✓", "✓"]},
    {"f": "Production after the trial", "m": ["—", "✓"]},
    {"f": "Becomes LGPL on Change Date", "m": ["✓", "✓"]}
  ],
  "footer": "Each module ships its own LICENSE file — the binding text · oduist.com/pricing"
}
```

## Notes

Legally sensitive post: every line is taken from
`connect/docs/admin/licensing.md`. Keep the "not legal advice" sentence and the
pointer to each module's LICENSE file. No prices in the post — link the pricing
page if asked.
