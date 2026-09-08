---
id: N05
title: A Markdown renderer with zero dependencies
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_book/docs/admin/book-setup.md]
---

## Post

We wrote our own Markdown renderer. Yes, we know how that sounds. 🙃

The reason is boring and decisive: an Odoo addon that needs `pip install` to render its own help page is an addon that fails to install on somebody's locked-down image. `connect_book` ships **no third-party package** and works in any Odoo environment.

What it deliberately covers:

📝 Headings, paragraphs, nested lists, fenced code, blockquotes, tables, rules, inline formatting
⚠️ MkDocs **admonitions** — `!!! note "Title"` with an indented body
🗂️ MkDocs **content tabs** — `=== "Label"` blocks, which the site renders as a switcher and the Book stacks as labelled panels, so every variant stays readable
✂️ YAML front matter stripped — it configures the site, not the Book
🤷 Anything outside that subset degrades to plain text instead of throwing

That's the trick: we didn't implement Markdown. We implemented **the subset this repository actually writes**, and made everything else harmless. A general-purpose parser would have been more code and more risk for zero extra pages rendered.

Vendoring a small parser vs adding a dependency — when do you think we called it wrong? 👇

#Odoo #Python #Markdown #Dependencies #SoftwareDesign

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Book",
  "headline": "Not a Markdown parser.",
  "headline_grad": "The subset we write.",
  "lede": "No third-party package, so it renders in any Odoo image. *Unsupported syntax degrades to plain text* rather than breaking a page.",
  "tiles": [
    {"sym": "#", "nm": "headings", "c": "cyan"},
    {"sym": "```", "nm": "fenced code", "c": "cyan"},
    {"sym": "▦", "nm": "tables", "c": "cyan"},
    {"sym": "!!!", "nm": "admonitions", "c": "magenta", "hero": true},
    {"sym": "===", "nm": "content tabs", "c": "magenta"},
    {"sym": "---", "nm": "front matter", "c": "core"}
  ],
  "footer": "Zero dependencies · content tabs become stacked labelled panels in Odoo"
}
```

## Notes

Scope claim is the documented one: the MkDocs subset used in this repository, not
CommonMark compliance. Do not claim full Markdown support in replies.
