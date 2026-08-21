# docs_site — Documentation Site Theme (Aurora on Tailwind)

## Site Info

- **Generator:** MkDocs (`mkdocs.yml` at the repository root)
- **Theme:** in-repo, `theme: name: null` + `custom_dir: docs/theme`
- **Styling:** Tailwind CSS v4 (CSS-first config, no `tailwind.config.js`)
- **Aggregation:** `mkdocs-monorepo-plugin` — 26 per-module `mkdocs.yml` files
  joined into one nav via `!include`
- **Content:** 75 Markdown pages (~332 KB), of which 73 are plain Markdown
- **Publishing:** `mkdocs gh-deploy --remote-branch website` from
  `.github/workflows/docs.yml`; GitHub Pages serves the `website` branch
- **Decision:** ADR-050

## Overview

The site's presentation layer is owned by this repository: templates, tokens,
components and search all live under `docs/theme/` and `theme-src/`. MkDocs
provides page rendering, the nav tree and the search index; everything the
reader sees is ours.

The visual language is "Aurora" — the Oduist brand palette mirrored from
`PALETTE.md` / `global.css` of the oduist.com site. Dark is the default scheme
(the brand site is dark-only); a light scheme reuses the same hues at
AA-contrast values, plus three semantic accents (mint / amber / rose) for
callouts, which the brand trio does not cover.

This theme replaces Material for MkDocs without changing how the site looks.
Visual parity with the pre-migration site is the acceptance criterion.

## File Layout

```
mkdocs.yml                      # theme: name: null, custom_dir: docs/theme
package.json                    # @tailwindcss/cli + @tailwindcss/typography
package-lock.json

theme-src/
  app.css                       # @import "tailwindcss"; @theme tokens; @layer components
  pygments.css                  # generated once, Aurora-coloured Pygments tokens

docs/theme/                     # the theme itself
  base.html                     # page skeleton + Jinja blocks
  main.html                     # {% extends "base.html" %} — the only page template
  404.html                      # via theme.static_templates
  partials/
    header.html  nav.html  nav-item.html  breadcrumbs.html
    toc.html  search.html  footer.html
  assets/
    app.css                     # Tailwind build output — COMMITTED (see Build)
    theme.js                    # entry point — wires the js/ modules up on DOM ready
    js/
      scheme.js                 # dark/light toggle, anti-flash persistence
      toc.js                    # TOC scrollspy
      drawer.js                 # mobile navigation drawer
      copy.js                   # copy-to-clipboard buttons, table wrapping
      search.js                 # search dialog, lunr index, result rendering
    vendor/lunr.min.js          # search engine (not shipped by the search plugin)

docs/javascripts/               # unchanged, loaded via extra_javascript
  hero-zoom.js  module-table.js
```

Deleted by this work: `docs/stylesheets/aurora.css`, `docs/overrides/`.
`docs/stylesheets/module-table.css` moves into `theme-src/app.css` as a
`@layer components` block; `extra_css` disappears from `mkdocs.yml`.

### Why templates and assets can share one directory

MkDocs excludes `*.html` from the files it copies out of a theme directory
(`mkdocs/structure/files.py:151`) and renders only the templates named in
`theme.static_templates` (default `404.html`, `sitemap.xml`) plus `main.html`
per page. Templates and partials therefore sit at the theme root; anything that
must reach `site/` goes under `assets/`.

## `mkdocs.yml` Changes

Removed: `theme.name: material`, `theme.palette`, `theme.features`,
`theme.font`, `theme.logo`, `theme.favicon`, `extra.generator`,
`extra_css`.

Added / changed:

```yaml
theme:
  name: null
  custom_dir: docs/theme
  static_templates:
    - 404.html

repo_url: https://github.com/oduist/connect_addons_ng
edit_uri: edit/19.0/docs/
```

Unchanged: `site_name`, `copyright`, `docs_dir`, `exclude_docs`, `plugins`
(`search`, `monorepo`), the whole `nav` block with its 26 `!include` entries,
`markdown_extensions`, `extra_javascript`.

`repo_url` and `edit_uri` are new and exist only to drive the "Edit on GitHub"
link. Aggregated pages live in a temporary `docs_dir` built by
`mkdocs-monorepo-plugin`, which would make a naive `edit_url` point at a path
that does not exist in the repository; the plugin rewrites the URL back to the
owning module in `on_pre_page` (`mkdocs_monorepo_plugin/plugin.py:72`,
`edit_uri.py`). The link must be verified on a module page, not only on
`docs/index.md`.

`site_url` was later changed, deliberately, from
`https://oduist.github.io/connect_addons_ng/` to `""` (commit 5043b0d) so the
home page is not addressed by the repository name. That trade-off has a
concrete cost worth recording:

MkDocs derives `404.html`'s asset URLs and its "back to home" link from
`site_url`'s path component. With `site_url: ""` that path is empty, so the
built `404.html` links `assets/app.css` and home as absolute paths from the
domain root (`/assets/app.css`, `/`) rather than relative to wherever the page
actually lives. On the current deploy target — `website` branch served at the
repository root of a `*.github.io` custom/apex domain, or any path-less
`site_url` — those absolute paths are correct and 404.html looks and works
exactly like the rest of the site. They break specifically if the site is ever
served under a **project-pages path** (e.g.
`https://oduist.github.io/connect_addons_ng/`, GitHub Pages' default for a
repo without a custom domain): `/assets/app.css` and `/` then resolve above
the site root, so the 404 page renders unstyled and its home link leaves the
site entirely.
Every other page is unaffected — they link relatively, which is exactly what
motivated leaving `site_url` empty in the first place.

Setting `site_url` back to the full deployed URL (path included) fixes this:
MkDocs would then emit `/connect_addons_ng/assets/app.css` and
`/connect_addons_ng/` for 404.html, correct under a project-pages path, at the
cost of reintroducing the repository name into the canonical home address
that commit 5043b0d removed it for. Whether that trade is worth making is a
call for the repository owner, contingent on where the site ends up being
served — `site_url` is deliberately left as `""` here (see ADR-050).

`edit_uri` **must** literally contain `docs/` as a path segment — not just
`edit/19.0/`. `mkdocs_monorepo_plugin/edit_uri.py` rewrites the edit URL with a
plain substring replacement of the root `docs_dir` ("docs") against each
module's own `docs_dir` (e.g. "connect_twilio/docs"); if `edit_uri` does not
contain the string "docs", the replacement silently no-ops and every module
page falls back to the un-rewritten root `edit_uri`, producing a broken link
that points at a path that does not exist in the repository. Do not
"simplify" this back to `edit/19.0/` — it looks equivalent but breaks the
rewrite.

## Templates

Everything the templates read is MkDocs core context, not Material's:
`page.ancestors`, `page.parent`, `page.toc`, `page.meta`,
`page.previous_page` / `page.next_page`, `page.edit_url`, `nav.items`,
`nav.homepage`, `nav_item.active` / `.is_section` / `.is_page`.

### `base.html`

The skeleton: `<head>` (title, meta, Google Fonts link for Geist and Geist
Mono, the committed `assets/app.css`, the anti-flash scheme script), a skip
link, the header, a three-column body (sidebar / content / TOC), the footer,
and `assets/theme.js` as a deferred module. Jinja blocks: `htmltitle`,
`styles`, `content`, `scripts`.

### `main.html`

`{% extends "base.html" %}`; renders `page.content` inside the prose container.
It is the only page template. A landing template is deliberately **not** built:
MkDocs supports `template:` in a page's front matter
(`mkdocs/commands/build.py:210`) if one is ever needed.

`page.meta.hide` is honoured for `navigation` and `toc`, which is what
`docs/index.md` and `docs/changelog.md` already declare — their front matter
stays untouched.

### `partials/header.html`

Logo + `site_name` linking home, the search field, the scheme toggle, a link to
the GitHub repository, and — below the header, sticky — the breadcrumb trail.
On narrow screens the header collapses to two buttons (navigation, search).

### `partials/nav.html` + `nav-item.html`

The sidebar is scoped to a single module: the top-level loop is narrowed to
`page.ancestors | last`, so inside Twilio the sidebar lists Twilio's pages and
nothing else. Readers move between modules through the breadcrumb trail and
search. Root-level pages (Home, Changelog) have no ancestor and hide the
sidebar outright via their front matter.

This is a port of the logic currently in `docs/overrides/partials/nav.html`,
with its rationale comment, but written against our own markup instead of
Material's `md-nav` structure. Section expansion uses `<details>` driven by
`nav_item.active` — no JavaScript.

### `partials/breadcrumbs.html`

`nav.homepage` followed by `page.ancestors | reverse`. Sticky under the header,
because it is the only way back to Home and from there to the other modules.
Anchored headings keep a `scroll-margin-top` that clears both the header and
the trail.

### `partials/toc.html`

`page.toc` to depth 2, with an `IntersectionObserver` scrollspy setting
`aria-current` on the active entry. On narrow screens it is not sticky
(`position: static`) and renders inline as a plain block below the content —
no `<details>` collapse was built; an earlier draft of this spec described
one, but it never shipped.

### `partials/footer.html`

Copyright, and prev/next links from `page.previous_page` / `page.next_page`
showing the neighbouring page titles. The "Edit on GitHub" link renders from
`page.edit_url` when set.

### `partials/search.html`

The search field markup plus the `<dialog>` that holds results. Behaviour lives
in `theme.js` (see Search).

## Tokens and Styles

### Tokens

`aurora.css` is two layers today: the `--au-*` palette (mirror of the brand
site) and a bridge pointing Material's `--md-*` properties at it. The bridge
disappears. The palette moves verbatim into Tailwind's `@theme` block in
`theme-src/app.css` — `--color-au-cyan`, `--color-au-panel`, `--radius-au-lg`
and so on — which yields both utilities (`bg-au-panel`, `text-au-muted`) and
plain custom properties for hand-written rules.

The brand rules carried over from the current file stay in force: the
cyan → iris → fuchsia gradient is the only multi-hue decorative element (header
hairline, h1 rule, primary button), cyan doubles as the flat accent, and body
text holds ≥ 7:1 against the void background.

### Schemes

Scheme state moves from Material's `data-md-color-scheme` to `data-theme` on
`<html>`: `prefers-color-scheme` by default, overridden by an explicit choice
persisted in `localStorage`, applied by a small inline script in `<head>` so
the page never flashes the wrong scheme. Tailwind sees it through

```css
@custom-variant dark (&:where([data-theme="dark"], [data-theme="dark"] *));
```

Dark stays the default; light stays reachable from the header toggle.

### Content typography

`@tailwindcss/typography` provides the prose container, with `--tw-prose-*`
mapped onto the Aurora tokens. Everything prose does not cover is written in
`@layer components`.

### Code

`pymdownx.superfences` already highlights through Pygments, so the HTML class
names (`.highlight .k`) exist independently of the theme; only Material's
stylesheet for them disappears. `theme-src/pygments.css` is generated once in
Aurora colours and committed. The corpus needs five lexers (bash, yaml, python,
xml, ini); 41 of 66 fences carry no language and render unhighlighted, as they
do today.

The copy-to-clipboard button was a Material feature (`content.code.copy`); it
becomes ~20 lines in `theme.js` that inject a button into each `.highlight`
block.

### Markdown components

- **Admonitions** — five types only: `info`, `note`, `warning`, `tip`,
  `danger`. That is the complete set the 87 admonitions in the corpus use.
  **Deviation from the original plan:** styling is CSS only — a left border
  and an uppercase title in the type's accent color
  (`--admonition-accent`, `theme-src/app.css`). No per-type inline SVG icon
  mask shipped, and the original's tinted title strip (a background fill
  behind the title, not just colored text) did not carry over either; the
  admonition otherwise keeps the same border/background/radius chrome as
  before.
- **Tabs** — `pymdownx.tabbed` with `alternate_style: true` emits radio inputs;
  styling only, no JavaScript. Used in 6 files.
- **Tables** — present in 58 of 75 files, the most load-bearing component. Each
  gets a wrapper with `overflow-x: auto` so wide tables scroll inside the
  content column instead of the page.
- **`details`** — `pymdownx.details` is enabled and unused in the corpus; it
  inherits the admonition styling for free.

### Home-page components

`module-table.css` (the periodic table of modules, the category legend, the
hero screenshot lightbox and its magnifier hint) moves into `@layer components`
**with its class names unchanged**. That keeps `docs/index.md`'s hand-written
HTML and both JavaScript files working as-is. The single content edit in the
whole migration is replacing `md-button` / `md-button--primary` in
`docs/index.md` with the theme's own button classes.

## Search

The `search` plugin stays enabled and keeps doing what it does today: on
`on_post_build` it writes `search/search_index.json` into the site
(`mkdocs/contrib/search/__init__.py:95`). It does not ship a search engine —
Material hid one in its own web worker — so the theme vendors
`lunr.min.js` (~30 KB) under `docs/theme/assets/vendor/`.

The index format suits us: `search_index.py` emits one record per page **and**
one per section with its anchor (`location`, `title`, `text`), so results land
on the right heading.

Behaviour:

- The index (~500 KB raw, ~120 KB gzipped for this corpus) is fetched lazily on
  first use, never on page load. While lunr builds, the dialog shows an
  indexing state; building over this corpus takes a fraction of a second.
- The dialog opens from the header field, `/`, or `⌘K`/`Ctrl+K`. Arrow keys
  move, `Enter` navigates, `Esc` closes.
- Each result shows the section title, the owning module (derived from
  `location`) and a snippet with the matched terms highlighted.
- Following a result appends `?h=<query>`; on load the theme highlights the
  matched terms in the content, reproducing Material's `search.highlight`.

If client-side index building ever becomes noticeable, the plugin's
`prebuild_index: node` option can be enabled — Node is already in CI by then.

## Build

`package.json` carries two dependencies (`@tailwindcss/cli`,
`@tailwindcss/typography`) and three scripts:

| Script | Does |
|---|---|
| `npm run build:css` | `tailwindcss -i theme-src/app.css -o docs/theme/assets/app.css --minify` |
| `npm run watch:css` | the same with `--watch` |
| `npm run dev` | `watch:css` and `mkdocs serve` together |

There is no JavaScript bundler: `theme.js` is a plain ES module and lunr is
vendored as-is.

`docs/theme/assets/app.css` is committed. The cost is a generated file in git;
the benefit is that `mkdocs serve` and `mkdocs build` keep working for a
contributor who only edits Markdown and has no Node installed. To keep the
committed file honest, CI rebuilds it and fails on any difference:

```yaml
- run: npm ci && npm run build:css
- run: git diff --exit-code docs/theme/assets/app.css
```

`.github/workflows/docs.yml` gains `actions/setup-node` and those two steps
before `mkdocs gh-deploy`, plus an explicit `mkdocs build --strict` and a
`tools/check_docs_site.py site` run so the checker has a build directory to
inspect (`mkdocs gh-deploy` does not leave one behind); the `paths:` trigger
filter is extended with `theme-src/**`, `package.json` and
`package-lock.json`.
`docs/requirements.txt` drops `mkdocs-material` and keeps `mkdocs` and
`pymdown-extensions` (explicitly, since Material used to pull both in
transitively — `markdown_extensions` in `mkdocs.yml` uses `pymdownx.details`,
`pymdownx.superfences` and `pymdownx.tabbed`) and `mkdocs-monorepo-plugin`.

## Migration Order

One branch, `19.0-docs-tailwind-theme`, in this order:

1. **Scaffold** — `package.json`, `theme-src/app.css` with the Aurora tokens,
   `base.html` / `main.html` / `404.html`, `mkdocs.yml` switched to
   `name: null`.
2. **Navigation** — sidebar with module scoping, breadcrumbs, TOC with
   scrollspy, mobile drawer.
3. **Content** — prose on the tokens, Pygments stylesheet, five admonition
   types, tables, tabs, copy buttons.
4. **Search** — vendored lunr, dialog, in-page highlighting.
5. **Home page** — `module-table.css` into `@layer components`, `md-button`
   replaced in `docs/index.md`.
6. **Header & footer** — prev/next, Edit on GitHub (`repo_url`, `edit_uri`),
   scheme toggle, repository link.
7. **Cleanup** — delete `aurora.css` and `docs/overrides/`, drop
   `mkdocs-material` from `docs/requirements.txt`, add the CSS build steps to
   the workflow, and update `AGENTS.md` (its Key Files list still calls the
   site "MkDocs Material" and does not mention this spec).

Between steps 1 and 5 the site **builds but looks unfinished**: Material is
switched off at the first commit and the styles arrive in pieces. That is the
accepted cost of replacing the foundation outright rather than running two CSS
systems side by side.

## Verification

Reference screenshots are captured with `agent-browser` on the current site
**before** step 1, and re-captured after step 7 for comparison:

- Home (hero, module table, legend, lightbox)
- A module page carrying a table and an admonition
- A page with tabbed content
- `changelog`
- `404`
- Each of the above in both schemes, and at a narrow viewport

Plus:

- `mkdocs build --strict` — clean (it also catches broken internal links)
- `page.edit_url` resolves to the owning module's file for a page from a
  module, not only for `docs/index.md`
- Keyboard checklist: search opens and navigates by keyboard, scheme toggle
  does not flash on load, sidebar shows only the current module, TOC scrollspy
  tracks, copy button works, prev/next resolve, drawer opens and traps focus
- Contrast holds at the values the palette already guarantees (same tokens, so
  this is a spot-check, not a re-audit)

## Non-Goals

- No redesign: Aurora is reproduced one-to-one.
- No content rewriting: 73 of 75 pages are untouched; `docs/index.md` changes
  two class names.
- No changes to `hero-zoom.js` or `module-table.js`.
- No documentation versioning, i18n, or offline build.
- No Material features that the corpus does not use: icon shortcodes, content
  grids, code annotations, instant navigation.
