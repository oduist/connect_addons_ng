---
id: N10
title: Fail-soft docs — one bad file never takes the book down
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_book/docs/admin/book-setup.md]
---

## Post

A documentation viewer has one job on a bad day: show the other 200 pages. 🩹

`connect_book` renders our docs inside Odoo, and every failure mode in it is a *skip*, never a stack trace:

📦 A Markdown file over **1 MB** is left out of the book entirely — skipped, not truncated, with a warning in the server log
💥 A page that fails to render is dropped the same way. One malformed file costs you that page, not the book
🔤 Syntax outside the supported subset degrades to **plain text** instead of throwing
🔗 A link that resolves outside the module's `docs/` folder is rendered inert; a link to a page your book doesn't hold simply does nothing
⚡ Rendered pages are cached per worker, keyed by path **and modification time** — so a redeploy invalidates itself, with no cache flush and no restart

The design rule: a content bug should degrade the content, never the feature. Documentation is exactly the place where an exception is least useful, because the reader is already stuck.

Fail-soft or fail-loud for user-facing content? Tell me why this is wrong. 👇

#Odoo #Documentation #Reliability #SoftwareDesign #DeveloperExperience

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Book",
  "headline": "One bad file",
  "headline_grad": "loses one page.",
  "lede": "Every failure mode in the docs renderer is a skip with a log line. *A content bug degrades the content, never the feature.*",
  "tiles": [
    {"sym": "1MB", "nm": "skipped whole", "c": "core", "hero": true},
    {"sym": "err", "nm": "page dropped", "c": "core"},
    {"sym": "txt", "nm": "unknown syntax", "c": "cyan"},
    {"sym": "↗", "nm": "inert link", "c": "cyan"},
    {"sym": "---", "nm": "front matter", "c": "app"},
    {"sym": "mtime", "nm": "cache key", "c": "app"}
  ],
  "footer": "Warnings land in the server log · redeploy invalidates the cache by itself"
}
```

## Notes

The 1 MB limit and the drop-on-render-failure behaviour are documented in
book-setup.md. Both are per page, per module — the rest of the book is unaffected.
