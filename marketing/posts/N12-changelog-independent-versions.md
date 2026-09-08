---
id: N12
title: A changelog when every module versions independently
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [docs/changelog.md, AGENTS.md]
---

## Post

Our changelog has no version numbers in its headings. That's not laziness — it's the only honest option. 📅

Oduist Connect is ~25 Odoo modules, each carrying its own manifest version, each moving when *it* changes. Core is well ahead of the providers; every provider is ahead of the ones added after it. There is no single number that describes a release of "Connect", so inventing one would be marketing, not documentation.

What we do instead:

🗓️ Entries are grouped by the **month they shipped in**, under Keep a Changelog headings
🔢 The version of any given module is shown on its card in **Apps** — that's the authoritative number, and it's per module
🔍 Entries are reconstructed from the **changes themselves**, not from commit subjects — intent is not what shipped
🧹 Work nobody outside the repository would notice — refactors, formatting, tests, CI, version bumps — is deliberately left out
📌 And the manifest version moves on release boundaries, at most once per feature branch, never once per commit

A changelog is for the reader, not for the release process.

Umbrella version or per-module truth? Tell me why this is wrong. 👇

#Odoo #Changelog #Versioning #OpenSource #SoftwareEngineering

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Releases",
  "headline": "No umbrella version.",
  "headline_grad": "Dated entries instead.",
  "lede": "Every module versions on its own schedule, so *no single number describes a release* — the changelog groups by month and names the module.",
  "tiles": [
    {"sym": "25+", "nm": "modules", "c": "provider"},
    {"sym": "1", "nm": "version each", "c": "provider"},
    {"sym": "YYYY", "nm": "-MM headings", "c": "cyan", "hero": true},
    {"sym": "diff", "nm": "not commit msg", "c": "app"},
    {"sym": "CI", "nm": "left out", "c": "core"},
    {"sym": "Apps", "nm": "shows version", "c": "memory"}
  ],
  "footer": "Keep a Changelog format · one manifest bump per feature branch, not per commit"
}
```

## Notes

"~25 modules" is the count of `connect*` directories in the repo, including
bridges and sub-modules. Recount before publishing if modules were added.
