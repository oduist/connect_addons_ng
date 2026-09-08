---
id: F05
title: One number written three ways, one contact
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [docs/changelog.md, connect_crm/docs/configuration.md, connect_hr/docs/configuration.md, connect/docs/admin/core-setup.md]
---

## Post

`(415) 555-0134`. `00 1 415 555 0134`. `+14155550134`.

Three contacts in your database. One human being. 🙃

Every integration that matches calls to records eventually trips on this, so **Oduist Connect** normalises caller IDs to E.164 *before* it looks anything up:

☝️ The same number, however it was typed, resolves to one contact
🔁 Lookups try the stripped digits, the `+` form and the E.164 form
🧮 Admins choose the matching operation: exact `=` (fast) or `like` (tolerant of formatting)
🚧 Numbers shorter than the extension threshold are skipped, so an internal extension never matches a 10-digit customer number
🧩 The same normalisation feeds the CRM, Helpdesk and HR number lookups — one rule, not three

Boring? Absolutely. It's also the difference between a call history that fills itself and a duplicate-contact cleanup project.

What's the worst phone format your CRM has ever stored? 👇

#Odoo #DataQuality #CRM #Telephony #E164

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Matching",
  "headline": "Three formats.",
  "headline_grad": "One contact.",
  "lede": "Caller IDs are normalised to *E.164 before matching*, so formatting differences stop creating duplicate contacts.",
  "nodes": [
    {"t": "(415) 555-0134", "s": "00 1 415… · +1 415…", "c": "core"},
    {"t": "One contact", "s": "matched every time", "c": "app"}
  ],
  "link_label": "E.164",
  "footer": "Exact or pattern matching · internal extensions excluded by length"
}
```

## Notes

The E.164 normalisation change is recorded in the 2026-06 changelog entry. The
example numbers are from the reserved 555-01xx range.
