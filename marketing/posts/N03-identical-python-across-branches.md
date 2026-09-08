---
id: N03
title: Identical Python across three Odoo branches
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [AGENTS.md, specs/decisions/039-odoo-18-full-backport.md]
---

## Post

Our rule for supporting Odoo 17, 18 and 19: **the Python source is byte-identical on all three branches.** Not "mostly". Byte-identical. 🧬

That is an invariant, not a style preference, and it has a price we pay openly:

🌿 Only non-Python assets may differ between branches — XML views, QWeb templates, and per-series `migrations/` entry points
🔀 Where Odoo genuinely behaves differently, we branch *inside the same file* on `release.version_info[0]` — sanitize on Html fields, `check_access`, the `Constraint` class, `user_ids`
💀 Which means the 18.0 branch carries live code paths that never execute there. Dead code, shipped knowingly. That's the cost
🧵 When the branching starts to dominate a file, the fix is a thin compat helper the business logic calls uniformly — never a forked file
🎁 What it buys: a backport is a clean cherry-pick instead of a manual merge, review is trivial because only views changed, and the three series cannot silently drift into three products

Most teams fork the file. We think that's how you end up maintaining three products and calling it one.

Tell me why this is wrong. 👇

#Odoo #Python #SoftwareEngineering #Maintenance #OpenSource

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · Versioning",
  "headline": "Same Python on",
  "headline_grad": "17.0, 18.0 and 19.0.",
  "lede": "Byte-identical `.py` across series, version branching inside the file. *We ship dead code on purpose* — here is the trade.",
  "columns": ["Fork file", "Identical"],
  "rows": [
    {"f": "Backport is a cherry-pick", "m": ["—", "✓"]},
    {"f": "Review only sees view diffs", "m": ["—", "✓"]},
    {"f": "Branches cannot drift apart", "m": ["—", "✓"]},
    {"f": "No unreachable code paths", "m": ["✓", "—"]},
    {"f": "Per-series migrations allowed", "m": ["✓", "✓"]},
    {"f": "Version checks inside files", "m": ["—", "✗"]}
  ],
  "footer": "Only XML/QWeb assets and migrations/<series>/ may differ between branches"
}
```

## Notes

The "✗" row marks the accepted downside (noise from version branching), matching
the honest framing in the post. Keep both.
