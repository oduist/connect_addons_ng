---
id: O01
title: Introducing Connect Book — documentation inside Odoo
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_book/docs/user/reading-the-docs.md, connect_book/docs/admin/book-setup.md, docs/changelog.md]
---

## Post

Product documentation goes stale for one boring reason: it lives somewhere else. 📚

**Connect Book** puts the whole Oduist Connect manual inside Odoo — and only the pages of the modules you actually have installed. What you read always matches what you run.

📖 **Connect ▸ Documentation ▸ User Guide** for anyone with a Connect role; **Admin Guide** for Connect administrators, and the menu is simply invisible to everyone else
🔎 Table of contents on the left, page on the right. The search box filters the contents, so you land on a page instead of a results list
🔗 Cross-references jump inside the pane — you never leave Odoo or lose your place
🌍 Translated pages are served in your Odoo language, page by page, falling back to English
🧩 No second copy of anything: the Book reads the same Markdown files and the same navigation as the public docs site

There is no settings page. Install it, and the menu is there.

Where does your team read the docs for the tools they use daily — or do they just ask each other? 👇

#Odoo #Documentation #DevEx #OpenSource

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Book",
  "headline": "The manual moved",
  "headline_grad": "inside Odoo.",
  "lede": "One source, two readers: the public docs site and the in-app Book read *the same files* — so what you read matches what you run.",
  "nodes": [
    {"t": "Module docs/", "s": "same Markdown as the docs site", "c": "core"},
    {"t": "Odoo", "s": "Connect ▸ Documentation", "c": "app"}
  ],
  "link_label": "installed modules only",
  "footer": "User Guide & Admin Guide · filtered contents · per-page translations"
}
```

## Notes

Time-sensitive: this shipped in the 2026-08 changelog. Publish soon, or reframe
as evergreen ("how our documentation works") by dropping the launch framing —
the feature itself does not expire.
