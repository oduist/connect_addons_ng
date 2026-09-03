# ADR-050: Replace mkdocs-material with an in-repo Tailwind theme

## Status

Accepted

## Context

The documentation site (`mkdocs.yml`, `docs/`, 75 pages aggregated from 26
per-module `mkdocs.yml` files by `mkdocs-monorepo-plugin`) is built on
[Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) 9.7.6. The
brand look — the "Aurora" palette mirrored from the oduist.com site — is layered
on top of it in `docs/stylesheets/aurora.css` (511 lines).

That layering is the problem. Roughly half of `aurora.css` is not design at all;
it is a bridge that points Material's `--md-*` custom properties at the `--au-*`
brand tokens, plus per-component overrides written against Material's internal
class names (`.md-nav__link--active`, `.md-typeset .admonition.warning >
.admonition-title`, `[data-md-color-scheme="slate"]`). `docs/overrides/partials/
nav.html` goes further: it is a **fork of an upstream partial**, carrying a
"kept in sync with material/templates/partials/nav.html" note, so that the
sidebar can be scoped to a single module.

Three consequences follow:

- Every Material release can silently break the site, because the overrides
  depend on class names and DOM structure that upstream never promised to keep.
- The docs and the oduist.com landing page share a palette but not a
  vocabulary: the site is Tailwind, the docs are hand-written CSS against
  someone else's component set.
- Ordinary visual changes are expensive. Adjusting a component means finding
  which Material rule wins and out-specifying it, rather than editing the
  component.

The content itself turns out to depend on Material very little. A scan of all
75 pages found: 87 admonitions in five flavours (info 30, note 29, warning 22,
tip 4, danger 2), tables in 58 files, tabbed blocks in 6 files, 9 images,
66 code fences (41 without a language), raw HTML and front matter in
`docs/index.md` alone — and **zero** uses of `:material-icon:` shortcodes,
content grids, or code annotations. Nothing in the corpus is locked to Material.

## Decision

Drop `mkdocs-material` entirely and ship an in-repo MkDocs theme
(`theme: name: null` + `custom_dir: docs/theme`) styled with Tailwind CSS v4.
MkDocs, `mkdocs-monorepo-plugin`, the `search` plugin, the `nav` tree and every
Markdown extension stay exactly as they are; only the presentation layer is
replaced. The full design — file layout, templates, tokens, search, build
pipeline, migration order — is specified in `specs/docs_site.md`.

Deliberate constraints on the change:

- **The site must look the same afterwards.** Aurora is kept one-to-one; this
  is a re-platforming, not a redesign. Visual parity is the acceptance test.
- **Content is not touched.** 73 of 75 pages are plain Markdown and stay
  untouched; only `docs/index.md` changes, to replace the two `md-button`
  classes it uses in its hand-written hero.
- **Only what the corpus uses gets built.** Five admonition types, not
  Material's fourteen; no icon shortcodes; no content grids.

Alternatives considered:

- **Fork Material's templates as a starting point.** Fastest route to a working
  site, but it carries over the `md-*` class architecture and the
  `data-md-component` JS contract — the dependency would survive, merely
  undeclared. Rejected: it defeats the purpose.
- **Strangler: Tailwind alongside Material, template by template.** Keeps the
  site fully styled at every step, but means two CSS foundations coexisting,
  with Tailwind's preflight fighting Material's base styles for the duration.
  Rejected: the conflict costs more than a few unpolished intermediate commits.
- **Move to a JS documentation generator** (Astro Starlight, VitePress,
  Docusaurus). Native Tailwind, but the 26-module aggregation that
  `mkdocs-monorepo-plugin` gives for free would have to be rebuilt, and all 75
  pages re-verified for syntax compatibility. Rejected: large blast radius for
  a presentation-layer goal.

## Consequences

- `docs/requirements.txt` loses `mkdocs-material`; the docs build gains a Node
  toolchain (`@tailwindcss/cli`, `@tailwindcss/typography`) and a
  `npm run build:css` step in `.github/workflows/docs.yml`.
- The generated `docs/theme/assets/app.css` **is committed**, so `mkdocs serve`
  and `mkdocs build` keep working for anyone who only edits Markdown and has no
  Node installed. CI rebuilds it and fails if the result differs from what is
  committed.
- Search is no longer free. The `search` plugin only emits
  `search/search_index.json`; the theme must vendor lunr and implement the
  search UI itself (~200 lines). This is the largest single piece of new code.
- `docs/stylesheets/aurora.css` and `docs/overrides/` are deleted;
  `docs/stylesheets/module-table.css` moves into the theme source as a Tailwind
  `@layer components` block, with its class names preserved so
  `docs/javascripts/hero-zoom.js` and `module-table.js` keep working unchanged.
- The site gains two things Material provided by configuration rather than by
  design: prev/next links in the footer and an "Edit on GitHub" link (which
  requires `repo_url` and `edit_uri` in `mkdocs.yml`; `mkdocs-monorepo-plugin`
  rewrites `page.edit_url` back to the owning module's path, see
  `mkdocs_monorepo_plugin/edit_uri.py`).
- Material upgrades stop being a risk, and stop being a source of features. Any
  future documentation feature — versioning, i18n, content tabs sync — is now
  ours to build.

## References

- `specs/docs_site.md` — the theme specification
- `mkdocs.yml`, `.github/workflows/docs.yml`
- Current implementation being replaced: `docs/stylesheets/aurora.css`,
  `docs/stylesheets/module-table.css`, `docs/overrides/partials/nav.html`
