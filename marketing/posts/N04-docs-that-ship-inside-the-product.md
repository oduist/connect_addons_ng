---
id: N04
title: Documentation that ships inside the product
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_book/docs/admin/book-setup.md, connect_book/docs/user/reading-the-docs.md, specs/decisions/059-connect-book-reads-the-mkdocs-tree.md]
---

## Post

Every documentation site eventually documents features the reader doesn't have. Different edition, older version, module never installed. 📚

So we made the docs read the database.

`connect_book` serves the documentation inside Odoo, and it does it without a second copy of anything:

📁 Each module keeps its pages in its own `docs/` folder. MkDocs builds the public site from those files; the Book reads **the same files**. No export step, no sync job
🔎 The Book lists only modules whose state is `installed`. A module sitting on disk but not installed contributes nothing — so the manual always matches the deployment
🗂️ Page titles and page order come from the module's own `mkdocs.yml` `nav` — one contract, two readers
👥 Audience is decided by the `nav` section, then the `docs/admin/` or `docs/user/` path, then a default of *admin* — a page never leaks to a wider audience because someone forgot to classify it
🌐 Translations are per page, with fallback to English, so a half-translated module is still fully readable

Docs as a deployed artefact, not a website you hope is current.

Where does this break down for you? 👇

#Odoo #Documentation #MkDocs #DeveloperExperience #OpenSource

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Book",
  "headline": "One folder of docs.",
  "headline_grad": "Two readers.",
  "lede": "MkDocs builds the site, `connect.book` builds the in-Odoo guides — *from the same Markdown and the same nav.*",
  "nodes": [
    {"t": "<module>/docs/*.md", "s": "titles & order from mkdocs.yml nav", "c": "app"},
    {"t": "Documentation in Odoo", "s": "User Guide · Admin Guide", "c": "cyan"}
  ],
  "link_label": "installed modules only",
  "footer": "Audience from nav section → path prefix → admin by default · per-page translations"
}
```

## Notes

`connect.book` is an abstract model — nothing stored, no access rules on it; the
group check runs on every call, not just on the menu.
