# Docs Tailwind Theme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Material for MkDocs with an in-repo MkDocs theme styled with Tailwind CSS v4, keeping the site's appearance, content and build pipeline unchanged.

**Architecture:** MkDocs keeps rendering pages, aggregating 26 module `mkdocs.yml` files through `mkdocs-monorepo-plugin` and emitting the search index. Everything the reader sees moves in-repo: Jinja templates under `docs/theme/`, Aurora brand tokens and components in `theme-src/app.css` compiled by the Tailwind CLI into a committed `docs/theme/assets/app.css`, and a handful of small ES modules for the behaviour Material used to provide (scheme toggle, TOC scrollspy, code copy, search, mobile drawer).

**Tech Stack:** MkDocs 1.6, mkdocs-monorepo-plugin 1.1.2, Tailwind CSS v4 (`@tailwindcss/cli`, `@tailwindcss/typography`), lunr.js (vendored), Pygments (via `pymdownx.superfences`), Python 3.12, Node 20, GitHub Actions.

**Spec:** `specs/docs_site.md` (decision: `specs/decisions/050-docs-custom-tailwind-theme.md`)

## Global Constraints

- **Visual parity is the acceptance test.** The Aurora palette is reproduced one-to-one; this is a re-platforming, not a redesign.
- **Content is not rewritten.** 73 of 75 Markdown pages stay byte-identical. The only content edit in the whole plan is replacing `md-button` / `md-button--primary` in `docs/index.md` (Task 6).
- **Only what the corpus uses gets built:** five admonition types (`info`, `note`, `warning`, `tip`, `danger`), tables, `pymdownx.tabbed` tabs, five Pygments lexers (bash, yaml, python, xml, ini). No icon shortcodes, no content grids, no code annotations, no instant navigation.
- **`docs/theme/assets/app.css` is committed** and must always match a fresh `npm run build:css`. CI enforces this with `git diff --exit-code`.
- **Class names of the home-page components are preserved** (`hero-art*`, `hero-zoom*`, `mod-*`) so `docs/javascripts/hero-zoom.js` and `docs/javascripts/module-table.js` keep working untouched.
- **Comments in English**, in every file type (repo rule, `AGENTS.md`).
- **Branch:** `19.0-docs-tailwind-theme`. Commit subjects use `[misc] <lowercase imperative>` — this work spans no single Odoo module.
- **Python venv for docs:** `.venv-docs/` already exists at the repo root with the current docs dependencies installed. Use `.venv-docs/bin/mkdocs` for every build command below.

**Refinement of the spec:** the spec names a single `docs/theme/assets/theme.js`. This plan splits it into focused ES modules under `docs/theme/assets/js/` (one per behaviour) with `theme.js` as the entry point, because the tasks below touch them independently. Task 8 updates the spec's file layout to match.

---

### Task 1: Baseline capture, build checker, npm toolchain

Nothing is replaced yet. This task produces the two things every later task is graded against: reference screenshots of the current site, and a script that asserts structural invariants of the built site.

**Files:**
- Create: `package.json`
- Create: `tools/check_docs_site.py`
- Create: `.gitignore` entry for `node_modules/` (append to the existing root `.gitignore`)
- Reference screenshots: `/tmp/docs-baseline/*.png` (throwaway; regenerate from this commit at any time)

**Interfaces:**
- Consumes: nothing.
- Produces: `python3 tools/check_docs_site.py` — exits 0 when every assertion passes, prints `FAIL: <message>` and exits 1 otherwise. Later tasks add assertions to its `CHECKS` list. `npm run build:css` — compiles `theme-src/app.css` into `docs/theme/assets/app.css`.

- [ ] **Step 1: Serve the current site**

```bash
.venv-docs/bin/mkdocs serve -a 127.0.0.1:8000
```

Run it in the background; leave it up for the next step.

- [ ] **Step 2: Capture the reference screenshots**

Use the `agent-browser` skill. Capture each of these, in **both** schemes (use the header toggle), at 1280px wide, then the Home page again at 390px wide:

| File | URL | Why this page |
|---|---|---|
| `home` | `/` | hero, module table, legend, lightbox |
| `module-table-admonition` | `/Twilio/configuration/` | a table plus admonitions |
| `tabs` | `/FreeSWITCH/admin/freeswitch-setup/` | tabbed content |
| `changelog` | `/changelog/` | long plain page, no sidebar |
| `notfound` | `/no-such-page/` | 404 template |

```bash
mkdir -p /tmp/docs-baseline
agent-browser open http://127.0.0.1:8000/
agent-browser screenshot /tmp/docs-baseline/home-dark.png
# ...toggle scheme, repeat as -light.png; then the remaining URLs
```

Confirm each PNG opens and shows the expected page (`Read` the files). Stop the server afterwards.

- [ ] **Step 3: Write the build checker**

Create `tools/check_docs_site.py`:

```python
#!/usr/bin/env python3
"""Structural assertions for the built documentation site.

Run after `mkdocs build`. The docs site has no unit tests: these checks are the
regression net for the theme's templates — every invariant a task establishes
gets an assertion here, so a later task cannot silently break it.

Usage: python3 tools/check_docs_site.py [site_dir]
"""

import pathlib
import re
import sys

SITE = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "site")

# One representative page per template path through the site.
HOME = SITE / "index.html"
MODULE_PAGE = SITE / "Twilio" / "configuration" / "index.html"
CHANGELOG = SITE / "changelog" / "index.html"
NOT_FOUND = SITE / "404.html"

failures = []


def check(name):
    """Register a check. Each returns None on success or a failure message."""

    def register(fn):
        fn.check_name = name
        CHECKS.append(fn)
        return fn

    return register


CHECKS = []


def read(path):
    if not path.exists():
        raise AssertionError(f"{path} was not built")
    return path.read_text(encoding="utf-8")


@check("every representative page was built")
def _pages_exist():
    for path in (HOME, MODULE_PAGE, CHANGELOG, NOT_FOUND):
        if not path.exists():
            return f"{path} is missing"


@check("pages link the compiled stylesheet")
def _stylesheet_linked():
    for path in (HOME, MODULE_PAGE, NOT_FOUND):
        html = read(path)
        if "assets/app.css" not in html:
            return f"{path} does not link assets/app.css"


@check("the search index was emitted")
def _search_index():
    if not (SITE / "search" / "search_index.json").exists():
        return "search/search_index.json is missing"


def main():
    for fn in CHECKS:
        try:
            problem = fn()
        except AssertionError as exc:
            problem = str(exc)
        if problem:
            failures.append(f"{fn.check_name}: {problem}")

    for failure in failures:
        print(f"FAIL: {failure}")
    if failures:
        print(f"\n{len(failures)} of {len(CHECKS)} checks failed")
        return 1
    print(f"OK: {len(CHECKS)} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the checker against the current site — it must pass**

```bash
.venv-docs/bin/mkdocs build
python3 tools/check_docs_site.py
```

Expected: `FAIL: pages link the compiled stylesheet: site/index.html does not link assets/app.css` — the site is still on Material, which links its own bundle. This confirms the checker actually inspects output. Temporarily nothing else should fail.

Leave that failure standing: Task 2 makes it pass. Note the two other checks passing.

- [ ] **Step 5: Create `package.json`**

```json
{
  "name": "connect-addons-ng-docs",
  "private": true,
  "description": "Build pipeline for the documentation site's Tailwind theme.",
  "scripts": {
    "build:css": "tailwindcss --input theme-src/app.css --output docs/theme/assets/app.css --minify",
    "watch:css": "tailwindcss --input theme-src/app.css --output docs/theme/assets/app.css --watch",
    "dev": "npm run watch:css & .venv-docs/bin/mkdocs serve"
  },
  "devDependencies": {
    "@tailwindcss/cli": "^4.1.0",
    "@tailwindcss/typography": "^0.5.16"
  }
}
```

- [ ] **Step 6: Install and confirm the CLI runs**

```bash
npm install
npx tailwindcss --help | head -5
```

Expected: the Tailwind v4 CLI usage banner. `npm install` also writes `package-lock.json` — it is committed.

- [ ] **Step 7: Ignore `node_modules`**

Append to the root `.gitignore`:

```
# Documentation theme build (Tailwind CLI)
node_modules/
```

- [ ] **Step 8: Commit**

```bash
git add package.json package-lock.json tools/check_docs_site.py .gitignore
git commit -m "[misc] add the docs theme build toolchain and a site checker"
```

---

### Task 2: Theme scaffold and Aurora tokens

The site switches off Material and onto the new theme. After this task it builds and is readable — header, content column, correct colours and fonts — but navigation, search and components are still missing. That is expected and stated in the spec.

**Files:**
- Create: `theme-src/app.css`
- Create: `docs/theme/base.html`, `docs/theme/main.html`, `docs/theme/404.html`
- Create: `docs/theme/assets/js/scheme.js`, `docs/theme/assets/theme.js`
- Create (generated, committed): `docs/theme/assets/app.css`
- Modify: `mkdocs.yml` (the `theme:` block)
- Modify: `tools/check_docs_site.py`

**Interfaces:**
- Consumes: `npm run build:css` from Task 1.
- Produces:
  - Jinja blocks in `base.html`: `htmltitle`, `styles`, `content`, `scripts`.
  - Partial include points, in this order inside `base.html`: `partials/header.html`, `partials/breadcrumbs.html`, `partials/nav.html`, `partials/toc.html`, `partials/footer.html`. Task 3 and Task 7 fill them in; Task 2 creates them as empty files so the includes resolve.
  - CSS custom properties `--color-au-*`, `--radius-au-*` available as Tailwind utilities (`bg-au-panel`, `text-au-muted`, `rounded-au-lg`).
  - `data-theme="dark" | "light"` on `<html>`, set before first paint.
  - `docs/theme/assets/js/scheme.js` exports `initScheme()`, called from `theme.js`.

- [ ] **Step 1: Add the assertions this task must satisfy**

In `tools/check_docs_site.py`, add:

```python
@check("pages carry the theme skeleton")
def _skeleton():
    html = read(MODULE_PAGE)
    for marker in ('data-theme=', 'class="docs-content', "assets/theme.js"):
        if marker not in html:
            return f"{marker!r} missing from {MODULE_PAGE}"


@check("no Material markup survives")
def _no_material():
    for path in (HOME, MODULE_PAGE, CHANGELOG):
        html = read(path)
        if "md-header" in html or "data-md-color-scheme" in html:
            return f"{path} still contains Material markup"
```

- [ ] **Step 2: Run the checker — the new checks must fail**

```bash
.venv-docs/bin/mkdocs build && python3 tools/check_docs_site.py
```

Expected: `FAIL: pages carry the theme skeleton` and `FAIL: no Material markup survives` (plus the stylesheet check still failing from Task 1).

- [ ] **Step 3: Write the Tailwind entry with the Aurora tokens**

Create `theme-src/app.css`. The token values are copied verbatim from `docs/stylesheets/aurora.css:31-77` (that file is deleted in Task 8, so copy before then):

```css
/*
 * "Aurora" — the Oduist Connect brand palette, now owned by this theme.
 *
 * Source of truth: PALETTE.md / global.css in the oduist-com site; values are
 * mirrored here 1:1. Brand rules carried over from DESIGN.md:
 *   - One Gradient: cyan -> iris -> fuchsia is the only multi-hue decorative
 *     element (header hairline, h1 rule, primary button). Cyan doubles as the
 *     flat accent.
 *   - Neutrals are subtly cool; body text >= 7:1 on the void background.
 *
 * Deviation, deliberate: the brand site is dark-only, but a docs site needs a
 * light mode, and admonitions need semantic (not decorative) colors. The light
 * scheme reuses the brand hues at darker, AA-contrast values, and three
 * semantic accents (mint / amber / rose) sit alongside the brand trio.
 */
@import "tailwindcss";
@plugin "@tailwindcss/typography";

/* Scheme is an explicit attribute on <html>, written before first paint by
   assets/js/scheme.js, so there is no flash of the wrong palette. */
@custom-variant dark (&:where([data-theme="dark"], [data-theme="dark"] *));

@theme {
  /* Brand */
  --color-au-cyan: #2dd4ff;    /* gradient 0%   · flat primary accent */
  --color-au-iris: #7c83ff;    /* gradient 42%  · focus ring · glow drop */
  --color-au-fuchsia: #e16bff; /* gradient 100% */
  --color-au-soft: #c9ccff;    /* soft highlight */

  /* Accent aliases */
  --color-au-signal-bright: #5cdcff; /* links / bright icons */
  --color-au-signal-deep: #1a86b0;   /* selection background, rails */
  --color-au-signal-faint: rgb(45 212 255 / 0.14);
  --color-au-primary-ink: #06070d;   /* ink on gradient / cyan fills */

  /* Semantic accents (docs-only, harmonized with the brand trio) */
  --color-au-mint: #2ee6a8;
  --color-au-amber: #ffc14d;
  --color-au-rose: #ff5d7a;

  /* Radii */
  --radius-au-sm: 6px;
  --radius-au-md: 10px;
  --radius-au-lg: 12px;

  /* Geist is loaded from Google Fonts in base.html, as Material used to. */
  --font-sans: Geist, ui-sans-serif, system-ui, sans-serif;
  --font-mono: "Geist Mono", ui-monospace, SFMono-Regular, monospace;
}

/* Scheme-dependent surfaces. Dark is the brand look and the default. */
:root,
[data-theme="dark"] {
  --au-bg: #04050a;           /* page background (void) */
  --au-panel: #0e0f14;        /* card / panel / code surface */
  --au-panel-raised: #14161f; /* raised surface */
  --au-header-bg: rgb(4 5 10 / 0.8);
  --au-ink: #eef0fa;
  --au-muted: #9aa1bd;
  --au-faint: #5b6184;
  --au-border: rgb(255 255 255 / 0.08);
  --au-border-strong: rgb(255 255 255 / 0.16);
  --au-border-hover: rgb(255 255 255 / 0.28);
  --au-link: var(--color-au-signal-bright);
  --au-code-ink: #dfe3f5;
}

/* Light scheme: the brand hues darkened to hold AA contrast. The current site
   only overrides accents here and inherits Material's light neutrals, so these
   neutral values are new — check them against the reference screenshots. */
[data-theme="light"] {
  --au-bg: #ffffff;
  --au-panel: #f2f5f9;
  --au-panel-raised: #ffffff;
  --au-header-bg: rgb(255 255 255 / 0.86);
  --au-ink: #14161f;
  --au-muted: #4d5470;
  --au-faint: #6b7392;
  --au-border: rgb(0 0 0 / 0.1);
  --au-border-strong: rgb(0 0 0 / 0.2);
  --au-border-hover: rgb(0 0 0 / 0.32);
  --au-link: var(--color-au-signal-deep);
  --au-code-ink: #1f2333;
}

/* The one gradient. */
:root {
  --au-gradient: linear-gradient(
    100deg, var(--color-au-cyan) 0%, var(--color-au-iris) 42%,
    var(--color-au-fuchsia) 100%);
}

@layer base {
  html {
    background-color: var(--au-bg);
    color: var(--au-ink);
    scroll-behavior: smooth;
  }

  /* Anchored headings must clear both the sticky header and the breadcrumb
     trail beneath it. */
  :target {
    scroll-margin-top: 7rem;
  }

  a {
    color: var(--au-link);
  }

  ::selection {
    background-color: var(--color-au-signal-deep);
    color: var(--color-au-primary-ink);
  }

  :focus-visible {
    outline: 2px solid var(--color-au-iris);
    outline-offset: 2px;
  }
}

@layer components {
  .docs-shell {
    display: grid;
    grid-template-columns: 16rem minmax(0, 1fr) 14rem;
    gap: 2.5rem;
    max-width: 84rem;
    margin-inline: auto;
    padding: 1.5rem 1.5rem 4rem;
  }

  @media (width < 76rem) {
    .docs-shell {
      grid-template-columns: minmax(0, 1fr);
    }
  }

  .skip-link {
    position: absolute;
    left: -9999px;
  }

  .skip-link:focus {
    left: 1rem;
    top: 1rem;
    z-index: 50;
    padding: 0.5rem 0.9rem;
    border-radius: var(--radius-au-md);
    background-color: var(--au-panel-raised);
  }
}
```

- [ ] **Step 4: Write the scheme module**

Create `docs/theme/assets/js/scheme.js`:

```js
// Colour-scheme toggle. The attribute is written twice: once by the inline
// snippet in base.html (before first paint, so the page never flashes the
// wrong palette) and again here, when the reader clicks the toggle.
const KEY = "docs-scheme";

export function initScheme() {
  const button = document.querySelector("[data-scheme-toggle]");
  if (!button) return;

  button.addEventListener("click", () => {
    const next =
      document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem(KEY, next);
    button.setAttribute("aria-pressed", String(next === "dark"));
  });
}
```

Create `docs/theme/assets/theme.js`:

```js
// Theme entry point. Every behaviour lives in its own module under js/; this
// file only wires them up on DOM ready.
import { initScheme } from "./js/scheme.js";

initScheme();
```

- [ ] **Step 5: Write `base.html`**

Create `docs/theme/base.html`:

```html
{#-
  Page skeleton for the Aurora theme (specs/docs_site.md).

  Everything read from the template context is MkDocs core: page.meta,
  page.toc, page.ancestors, nav.items, config.*. Nothing here depends on a
  third-party theme.
-#}
<!DOCTYPE html>
<html lang="en" data-theme="dark">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block htmltitle %}{% if page.title and not page.is_homepage %}{{ page.title }} — {{ config.site_name }}{% else %}{{ config.site_name }}{% endif %}{% endblock %}</title>
    {% if config.site_description %}
      <meta name="description" content="{{ config.site_description }}">
    {% endif %}
    <link rel="icon" href="{{ 'assets/logo.png' | url }}">
    {#- Written before first paint so the page never flashes the wrong palette. -#}
    <script>
      (function () {
        var stored = null;
        try { stored = localStorage.getItem("docs-scheme"); } catch (e) {}
        var prefersLight =
          window.matchMedia("(prefers-color-scheme: light)").matches;
        document.documentElement.dataset.theme =
          stored || (prefersLight ? "light" : "dark");
      })();
    </script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500&display=swap">
    {% block styles %}
      <link rel="stylesheet" href="{{ 'theme/assets/app.css' | url }}">
    {% endblock %}
  </head>
  <body>
    <a class="skip-link" href="#docs-main">Skip to content</a>
    {% include "partials/header.html" %}
    {% include "partials/breadcrumbs.html" %}

    <div class="docs-shell">
      {% if "navigation" not in (page.meta.hide or []) %}
        {% include "partials/nav.html" %}
      {% endif %}

      <main id="docs-main" class="docs-content">
        {% block content %}{% endblock %}
      </main>

      {% if "toc" not in (page.meta.hide or []) %}
        {% include "partials/toc.html" %}
      {% endif %}
    </div>

    {% include "partials/footer.html" %}

    {% block scripts %}
      <script type="module" src="{{ 'theme/assets/theme.js' | url }}"></script>
      {% for path in config.extra_javascript %}
        <script src="{{ path | url }}"></script>
      {% endfor %}
    {% endblock %}
  </body>
</html>
```

- [ ] **Step 6: Write `main.html` and `404.html`**

`docs/theme/main.html`:

```html
{% extends "base.html" %}

{% block content %}
  <article class="prose max-w-none">
    {{ page.content }}
  </article>
{% endblock %}
```

`docs/theme/404.html`:

```html
{% extends "base.html" %}

{% block htmltitle %}Page not found — {{ config.site_name }}{% endblock %}

{% block content %}
  <article class="prose max-w-none">
    <h1>Page not found</h1>
    <p>
      That page does not exist. Try the
      <a href="{{ '/' | url }}">documentation home page</a>, or search from the
      header.
    </p>
  </article>
{% endblock %}
```

- [ ] **Step 7: Create the empty partials so the includes resolve**

```bash
mkdir -p docs/theme/partials
for p in header breadcrumbs nav toc footer; do
  printf '{#- Filled in by a later task (see docs/superpowers/plans). -#}\n' \
    > "docs/theme/partials/$p.html"
done
```

- [ ] **Step 8: Point `mkdocs.yml` at the new theme**

Replace the whole `theme:` block (currently `mkdocs.yml:18-60`) with:

```yaml
theme:
  name: null
  custom_dir: docs/theme
  static_templates:
    - 404.html
```

Delete the `extra:` block (`generator: false` was a Material setting) and the `extra_css:` block. Leave `plugins`, `nav`, `markdown_extensions` and `extra_javascript` untouched.

- [ ] **Step 9: Build the CSS and the site**

```bash
npm run build:css
.venv-docs/bin/mkdocs build --strict
python3 tools/check_docs_site.py
```

Expected: `mkdocs build --strict` succeeds; the checker prints `OK: 5 checks passed`.

- [ ] **Step 10: Look at it**

Serve and screenshot the module page in both schemes; confirm text is legible, the background is the void colour in dark and white in light, and Geist is loading. Broken navigation and unstyled admonitions are expected at this point.

- [ ] **Step 11: Commit**

```bash
git add theme-src docs/theme mkdocs.yml tools/check_docs_site.py
git commit -m "[misc] scaffold the in-repo docs theme on tailwind"
```

---

### Task 3: Navigation — sidebar, breadcrumbs, TOC, drawer

**Files:**
- Modify: `docs/theme/partials/nav.html`, `docs/theme/partials/breadcrumbs.html`, `docs/theme/partials/toc.html`, `docs/theme/partials/header.html`
- Create: `docs/theme/partials/nav-item.html`
- Create: `docs/theme/assets/js/toc.js`, `docs/theme/assets/js/drawer.js`
- Modify: `docs/theme/assets/theme.js`, `theme-src/app.css`, `tools/check_docs_site.py`

**Interfaces:**
- Consumes: the include points and `--au-*` tokens from Task 2.
- Produces:
  - `partials/nav-item.html` exposes the macro `render(nav_item, level)`, imported by `nav.html`.
  - Header markup with `[data-scheme-toggle]` (wired in Task 2), `[data-drawer-open]`, and a `<dialog data-drawer>` holding the sidebar on narrow screens.
  - `initToc()` and `initDrawer()` exported from their modules and called by `theme.js`.

- [ ] **Step 1: Add the assertions**

In `tools/check_docs_site.py`:

```python
@check("the sidebar is scoped to the current module")
def _sidebar_scope():
    html = read(MODULE_PAGE)
    if 'class="docs-nav"' not in html:
        return "no sidebar rendered on a module page"
    # The Twilio page must not advertise other modules in its sidebar.
    sidebar = html.split('class="docs-nav"', 1)[1].split("</nav>", 1)[0]
    for stranger in ("FreeSWITCH", "LiveKit", "Telnyx"):
        if stranger in sidebar:
            return f"sidebar leaks {stranger} on a Twilio page"


@check("root pages hide the sidebar")
def _root_pages_have_no_sidebar():
    if 'class="docs-nav"' in read(HOME):
        return "the home page renders a sidebar despite hide: navigation"


@check("breadcrumbs walk back to home")
def _breadcrumbs():
    html = read(MODULE_PAGE)
    if 'class="docs-crumbs"' not in html:
        return "no breadcrumb trail on a module page"
    crumbs = html.split('class="docs-crumbs"', 1)[1].split("</nav>", 1)[0]
    if "Twilio" not in crumbs or ">Home<" not in crumbs:
        return "breadcrumb trail does not run Home -> Twilio"


@check("the page TOC is rendered")
def _toc():
    if 'class="docs-toc"' not in read(MODULE_PAGE):
        return "no table of contents on a module page"
```

- [ ] **Step 2: Run the checker — the four new checks must fail**

```bash
.venv-docs/bin/mkdocs build && python3 tools/check_docs_site.py
```

Expected: 4 failures, 5 passes.

- [ ] **Step 3: Write the recursive nav item macro**

`docs/theme/partials/nav-item.html`:

```html
{#- One entry in the sidebar tree. Sections expand with <details>, driven by
    nav_item.active, so no JavaScript is involved. -#}
{% macro render(nav_item, level) %}
  {% if nav_item.children %}
    <li class="docs-nav__item">
      <details {% if nav_item.active %}open{% endif %}>
        <summary class="docs-nav__section">{{ nav_item.title }}</summary>
        <ul class="docs-nav__list">
          {% for child in nav_item.children %}
            {{ render(child, level + 1) }}
          {% endfor %}
        </ul>
      </details>
    </li>
  {% elif nav_item.is_page %}
    <li class="docs-nav__item">
      <a class="docs-nav__link{% if nav_item.active %} docs-nav__link--active{% endif %}"
         href="{{ nav_item.url | url }}"
         {% if nav_item.active %}aria-current="page"{% endif %}>
        {{ nav_item.title }}
      </a>
    </li>
  {% endif %}
{% endmacro %}
```

- [ ] **Step 4: Write the sidebar**

`docs/theme/partials/nav.html`:

```html
{#-
  Sidebar scoped to one module.

  The nav aggregates ~28 modules through mkdocs-monorepo-plugin. Rendering all
  of them buries the pages of the module actually being read, so the top-level
  loop is narrowed to the section the current page belongs to: inside Twilio
  the sidebar lists Twilio's pages and nothing else.

  Readers move between modules through the breadcrumb trail and search, not
  through the sidebar. Root-level pages (Home, Changelog) have no ancestor to
  scope to and hide the sidebar outright via "hide: navigation".
-#}
{% import "partials/nav-item.html" as item with context %}
{% set root = (page.ancestors | last) if page and page.ancestors else none %}
<nav class="docs-nav" aria-label="Module navigation">
  <ul class="docs-nav__list">
    {% for nav_item in nav.items %}
      {% if root is none or nav_item == root %}
        {{ item.render(nav_item, 1) }}
      {% endif %}
    {% endfor %}
  </ul>
</nav>
```

- [ ] **Step 5: Write the breadcrumbs**

`docs/theme/partials/breadcrumbs.html`:

```html
{#- Sticky under the header: it is the only way back to Home, and from there to
    the other modules, so scrolling must not take it away. -#}
{% if page and page.ancestors %}
  <nav class="docs-crumbs" aria-label="Breadcrumb">
    <ol class="docs-crumbs__list">
      {% if nav.homepage %}
        <li><a href="{{ nav.homepage.url | url }}">Home</a></li>
      {% endif %}
      {% for ancestor in page.ancestors | reverse %}
        <li>
          {% if ancestor.url %}
            <a href="{{ ancestor.url | url }}">{{ ancestor.title }}</a>
          {% else %}
            <span>{{ ancestor.title }}</span>
          {% endif %}
        </li>
      {% endfor %}
      <li aria-current="page">{{ page.title }}</li>
    </ol>
  </nav>
{% endif %}
```

Note: a section's `url` is empty in MkDocs; the `{% else %}` branch renders it as text. If a section should be walkable, resolve it to its first child page — check the reference screenshots to see which behaviour the current site has, and match it.

- [ ] **Step 6: Write the TOC**

`docs/theme/partials/toc.html`:

```html
{#- Page contents, two levels deep, with a scrollspy in js/toc.js. Collapses
    into a <details> on narrow screens (CSS-driven). -#}
{% if page.toc %}
  <aside class="docs-toc" aria-label="On this page">
    <p class="docs-toc__title">On this page</p>
    <ul class="docs-toc__list">
      {% for entry in page.toc %}
        <li>
          <a class="docs-toc__link" href="{{ entry.url }}">{{ entry.title }}</a>
          {% if entry.children %}
            <ul class="docs-toc__list docs-toc__list--nested">
              {% for child in entry.children %}
                <li>
                  <a class="docs-toc__link" href="{{ child.url }}">{{ child.title }}</a>
                </li>
              {% endfor %}
            </ul>
          {% endif %}
        </li>
      {% endfor %}
    </ul>
  </aside>
{% endif %}
```

- [ ] **Step 7: Write the header**

`docs/theme/partials/header.html` (the search field is inert until Task 5; the repo link and prev/next arrive in Task 7):

```html
<header class="docs-header">
  <button class="docs-header__burger" type="button" data-drawer-open
          aria-label="Open navigation">☰</button>

  <a class="docs-header__brand" href="{{ nav.homepage.url | url }}">
    <img src="{{ 'assets/logo.png' | url }}" alt="" width="24" height="24">
    <span>{{ config.site_name }}</span>
  </a>

  <div class="docs-header__spacer"></div>

  <button class="docs-header__toggle" type="button" data-scheme-toggle
          aria-pressed="true" aria-label="Toggle colour scheme">
    <span class="docs-header__toggle-dark">Dark</span>
    <span class="docs-header__toggle-light">Light</span>
  </button>
</header>

<dialog class="docs-drawer" data-drawer aria-label="Navigation">
  <button class="docs-drawer__close" type="button" data-drawer-close
          aria-label="Close navigation">×</button>
  <div data-drawer-body></div>
</dialog>
```

- [ ] **Step 8: Write the TOC scrollspy and the drawer**

`docs/theme/assets/js/toc.js`:

```js
// Highlights the table-of-contents entry for the heading currently on screen.
export function initToc() {
  const links = [...document.querySelectorAll(".docs-toc__link")];
  if (!links.length) return;

  const byId = new Map();
  for (const link of links) {
    const id = decodeURIComponent(link.hash.slice(1));
    const heading = id && document.getElementById(id);
    if (heading) byId.set(heading, link);
  }

  let active = null;
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        const link = byId.get(entry.target);
        if (!link || link === active) continue;
        active?.removeAttribute("aria-current");
        link.setAttribute("aria-current", "true");
        active = link;
      }
    },
    // Only the band just below the sticky header counts as "current".
    { rootMargin: "-7rem 0px -70% 0px" },
  );

  for (const heading of byId.keys()) observer.observe(heading);
}
```

`docs/theme/assets/js/drawer.js`:

```js
// Mobile navigation. The sidebar exists once in the page; on narrow screens it
// is moved into a <dialog>, which gives focus trapping and Esc for free.
export function initDrawer() {
  const dialog = document.querySelector("[data-drawer]");
  const body = dialog?.querySelector("[data-drawer-body]");
  const nav = document.querySelector(".docs-nav");
  const openButton = document.querySelector("[data-drawer-open]");
  if (!dialog || !body || !nav || !openButton) return;

  openButton.addEventListener("click", () => {
    body.append(nav);
    dialog.showModal();
  });

  dialog.querySelector("[data-drawer-close]")?.addEventListener("click", () => {
    dialog.close();
  });

  // Put the sidebar back where the layout expects it once the drawer closes.
  dialog.addEventListener("close", () => {
    document.querySelector(".docs-shell")?.prepend(nav);
  });
}
```

Update `docs/theme/assets/theme.js`:

```js
// Theme entry point. Every behaviour lives in its own module under js/; this
// file only wires them up.
import { initScheme } from "./js/scheme.js";
import { initToc } from "./js/toc.js";
import { initDrawer } from "./js/drawer.js";

initScheme();
initToc();
initDrawer();
```

- [ ] **Step 9: Style the navigation**

Append to `theme-src/app.css`, inside `@layer components`:

```css
  .docs-header {
    position: sticky;
    top: 0;
    z-index: 30;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.6rem 1.5rem;
    background-color: var(--au-header-bg);
    backdrop-filter: blur(8px);
  }

  /* The one gradient, as the header's hairline. */
  .docs-header::after {
    content: "";
    position: absolute;
    inset-inline: 0;
    bottom: 0;
    height: 1px;
    background: var(--au-gradient);
  }

  .docs-header__brand {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-weight: 600;
    color: var(--au-ink);
    text-decoration: none;
  }

  .docs-header__spacer { flex: 1; }

  .docs-crumbs {
    position: sticky;
    top: 3.1rem;
    z-index: 20;
    padding: 0.5rem 1.5rem;
    background-color: var(--au-header-bg);
    backdrop-filter: blur(8px);
    border-bottom: 1px solid var(--au-border);
    font-size: 0.78rem;
    color: var(--au-muted);
  }

  .docs-crumbs__list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .docs-crumbs__list li + li::before {
    content: "/";
    margin-right: 0.35rem;
    color: var(--au-faint);
  }

  .docs-nav { align-self: start; position: sticky; top: 6.5rem; }

  .docs-nav__list { list-style: none; margin: 0; padding: 0; }

  .docs-nav__link {
    display: block;
    padding: 0.28rem 0.5rem;
    border-radius: var(--radius-au-sm);
    color: var(--au-muted);
    text-decoration: none;
    font-size: 0.86rem;
  }

  .docs-nav__link:hover { color: var(--au-ink); background-color: var(--au-panel); }

  .docs-nav__link--active {
    color: var(--color-au-cyan);
    background-color: var(--color-au-signal-faint);
  }

  /* Section headers are labels, not links — the plain arrow cursor says so. */
  .docs-nav__section {
    cursor: default;
    margin-top: 1.2rem;
    padding-top: 0.8rem;
    border-top: 1px solid var(--au-border);
    color: var(--au-muted);
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.09em;
    text-transform: uppercase;
  }

  .docs-toc { align-self: start; position: sticky; top: 6.5rem; font-size: 0.8rem; }
  .docs-toc__list { list-style: none; margin: 0; padding: 0; }
  .docs-toc__list--nested { padding-left: 0.75rem; }
  .docs-toc__link { color: var(--au-muted); text-decoration: none; }
  .docs-toc__link[aria-current] { color: var(--color-au-cyan); }

  .docs-drawer {
    width: min(20rem, 90vw);
    height: 100%;
    max-height: 100%;
    margin: 0 auto 0 0;
    border: 0;
    border-right: 1px solid var(--au-border);
    background-color: var(--au-panel);
    color: var(--au-ink);
  }

  .docs-drawer::backdrop { background-color: rgb(4 5 10 / 0.6); }

  @media (width >= 76rem) {
    .docs-header__burger { display: none; }
  }

  @media (width < 76rem) {
    .docs-toc { position: static; }
  }
```

- [ ] **Step 10: Build and check**

```bash
npm run build:css && .venv-docs/bin/mkdocs build --strict && python3 tools/check_docs_site.py
```

Expected: `OK: 9 checks passed`.

- [ ] **Step 11: Verify in the browser**

Serve, then confirm on a Twilio page: the sidebar lists only Twilio, the active page is highlighted, breadcrumbs read `Home / Twilio / …` and stay put when scrolling, the TOC highlight follows the scroll, and at 390px the burger opens a drawer that closes on `Esc`.

- [ ] **Step 12: Commit**

```bash
git add docs/theme theme-src/app.css tools/check_docs_site.py
git commit -m "[misc] give the docs theme its navigation, breadcrumbs and toc"
```

---

### Task 4: Content styles — prose, code, admonitions, tables, tabs

**Files:**
- Create: `theme-src/pygments.css`
- Create: `docs/theme/assets/js/copy.js`
- Modify: `theme-src/app.css`, `docs/theme/assets/theme.js`, `docs/theme/main.html`, `tools/check_docs_site.py`

**Interfaces:**
- Consumes: tokens and the prose container from Task 2.
- Produces: `initCopyButtons()` exported from `js/copy.js`; every `.highlight` block gains a `<button class="docs-copy">`.

- [ ] **Step 1: Add the assertions**

```python
@check("admonitions and tables are wrapped for styling")
def _content_components():
    html = read(MODULE_PAGE)
    if "admonition" not in html:
        return "expected an admonition on the Twilio configuration page"
    if 'class="docs-table-wrap"' not in html:
        return "tables are not wrapped for horizontal scrolling"


@check("code blocks carry Pygments classes")
def _code_highlighting():
    html = read(MODULE_PAGE)
    if 'class="highlight"' not in html:
        return "no highlighted code block found"
```

- [ ] **Step 2: Run the checker — both must fail**

Expected: 2 failures, 9 passes.

- [ ] **Step 3: Write the Pygments stylesheet**

Create `theme-src/pygments.css`. The token → colour mapping is the one the current site uses via Material's `--md-code-hl-*` variables (`docs/stylesheets/aurora.css:103-113`):

```css
/*
 * Pygments tokens in Aurora colours. pymdownx.superfences already emits these
 * class names; only Material's stylesheet for them went away.
 * Mapping preserved from the previous --md-code-hl-* assignments.
 */
.highlight pre { color: var(--au-code-ink); }

.highlight .k,  /* keyword */
.highlight .kd,
.highlight .kn,
.highlight .kr { color: var(--color-au-iris); }

.highlight .s,  /* string */
.highlight .s1,
.highlight .s2,
.highlight .sb,
.highlight .se { color: var(--color-au-cyan); }

.highlight .nf, /* function */
.highlight .fm { color: var(--color-au-signal-bright); }

.highlight .kc, /* constant */
.highlight .no,
.highlight .m,  /* number */
.highlight .mi,
.highlight .mf,
.highlight .o,  /* operator */
.highlight .ow { color: var(--color-au-fuchsia); }

.highlight .nv, /* variable */
.highlight .vi { color: var(--color-au-soft); }

.highlight .n,  /* name */
.highlight .nx,
.highlight .nt { color: var(--au-ink); }

.highlight .p { color: var(--au-muted); }  /* punctuation */

.highlight .c,  /* comment */
.highlight .c1,
.highlight .cm { color: var(--au-faint); font-style: italic; }

.highlight .err { color: var(--color-au-rose); }
```

Import it from `theme-src/app.css`, directly after the `@plugin` line:

```css
@import "./pygments.css";
```

- [ ] **Step 4: Map prose onto the Aurora tokens**

Append to `theme-src/app.css`:

```css
@layer components {
  .prose {
    --tw-prose-body: var(--au-ink);
    --tw-prose-headings: var(--au-ink);
    --tw-prose-links: var(--au-link);
    --tw-prose-bold: var(--au-ink);
    --tw-prose-counters: var(--au-muted);
    --tw-prose-bullets: var(--au-faint);
    --tw-prose-hr: var(--au-border);
    --tw-prose-quotes: var(--au-muted);
    --tw-prose-quote-borders: var(--au-border-strong);
    --tw-prose-code: var(--au-code-ink);
    --tw-prose-pre-code: var(--au-code-ink);
    --tw-prose-pre-bg: var(--au-panel);
    --tw-prose-th-borders: var(--au-border-strong);
    --tw-prose-td-borders: var(--au-border);
  }

  /* The one gradient, as the rule under the page title. */
  .prose h1 {
    padding-bottom: 0.4rem;
    border-bottom: 2px solid transparent;
    border-image: var(--au-gradient) 1;
  }

  .prose :not(pre) > code {
    padding: 0.15em 0.35em;
    border-radius: var(--radius-au-sm);
    background-color: var(--au-panel);
    font-weight: 400;
  }

  .prose :not(pre) > code::before,
  .prose :not(pre) > code::after { content: none; }

  /* Wide tables scroll inside the content column, never the page. */
  .docs-table-wrap {
    overflow-x: auto;
    margin-block: 1.4rem;
    border: 1px solid var(--au-border);
    border-radius: var(--radius-au-md);
  }

  .docs-table-wrap > table { margin: 0; }

  .highlight {
    position: relative;
    border: 1px solid var(--au-border);
    border-radius: var(--radius-au-md);
    background-color: var(--au-panel);
  }

  .docs-copy {
    position: absolute;
    top: 0.4rem;
    right: 0.4rem;
    padding: 0.2rem 0.5rem;
    border: 1px solid var(--au-border-strong);
    border-radius: 999px;
    background-color: var(--au-panel-raised);
    color: var(--au-muted);
    font-size: 0.7rem;
    opacity: 0;
    transition: opacity 150ms ease, color 150ms ease;
  }

  .highlight:hover .docs-copy,
  .docs-copy:focus-visible { opacity: 1; }

  /* Admonitions — the five types the corpus uses. */
  .admonition,
  details.admonition {
    margin-block: 1.4rem;
    border: 1px solid var(--au-border);
    border-left: 3px solid var(--admonition-accent, var(--color-au-cyan));
    border-radius: var(--radius-au-md);
    background-color: var(--au-panel);
    padding: 0.8rem 1rem;
  }

  .admonition-title {
    margin: 0 0 0.4rem;
    color: var(--admonition-accent, var(--color-au-cyan));
    font-weight: 600;
    font-size: 0.86rem;
    letter-spacing: 0.02em;
    text-transform: uppercase;
  }

  .admonition.note { --admonition-accent: var(--color-au-iris); }
  .admonition.info { --admonition-accent: var(--color-au-cyan); }
  .admonition.tip { --admonition-accent: var(--color-au-mint); }
  .admonition.warning { --admonition-accent: var(--color-au-amber); }
  .admonition.danger { --admonition-accent: var(--color-au-rose); }

  /* Tabs: pymdownx.tabbed with alternate_style renders radio inputs, so the
     switching is pure CSS. */
  .tabbed-set { margin-block: 1.4rem; }
  .tabbed-set > input { position: absolute; opacity: 0; }

  .tabbed-labels {
    display: flex;
    gap: 0.3rem;
    border-bottom: 1px solid var(--au-border);
  }

  .tabbed-labels > label {
    padding: 0.4rem 0.8rem;
    color: var(--au-muted);
    font-size: 0.86rem;
    cursor: pointer;
  }

  .tabbed-set > input:checked + .tabbed-labels > label,
  .tabbed-labels > label:hover { color: var(--au-ink); }
}
```

Tab-selection styling in `pymdownx.tabbed` relies on `:checked` sibling selectors whose exact shape depends on the number of tabs; after building, inspect one tabbed page and adjust the selector so the active label is underlined with `--color-au-cyan`.

- [ ] **Step 5: Wrap tables and add copy buttons**

`docs/theme/assets/js/copy.js`:

```js
// Two content fix-ups Material used to do for us.
export function initCopyButtons() {
  for (const block of document.querySelectorAll(".highlight")) {
    const code = block.querySelector("code");
    if (!code) continue;

    const button = document.createElement("button");
    button.type = "button";
    button.className = "docs-copy";
    button.textContent = "Copy";
    button.addEventListener("click", async () => {
      await navigator.clipboard.writeText(code.innerText);
      button.textContent = "Copied";
      setTimeout(() => (button.textContent = "Copy"), 1500);
    });
    block.append(button);
  }
}

export function wrapTables() {
  for (const table of document.querySelectorAll(".prose table")) {
    if (table.parentElement?.classList.contains("docs-table-wrap")) continue;
    const wrap = document.createElement("div");
    wrap.className = "docs-table-wrap";
    table.replaceWith(wrap);
    wrap.append(table);
  }
}
```

Wire both into `docs/theme/assets/theme.js` (add the import and the two calls next to the existing ones).

Note: `wrapTables()` runs client-side, so the `docs-table-wrap` assertion added in Step 1 would fail against static HTML. Change that assertion to check the CSS instead — replace the table clause with:

```python
    if "docs-table-wrap" not in (SITE / "theme" / "assets" / "app.css").read_text():
        return "the table wrapper class is not in the compiled stylesheet"
```

- [ ] **Step 6: Build and check**

```bash
npm run build:css && .venv-docs/bin/mkdocs build --strict && python3 tools/check_docs_site.py
```

Expected: `OK: 11 checks passed`.

- [ ] **Step 7: Compare against the baseline**

Screenshot `/Twilio/configuration/` and `/FreeSWITCH/admin/freeswitch-setup/` in both schemes and compare with `/tmp/docs-baseline/`. Admonition colours, code block surface and table rules should read the same. Fix what drifted.

- [ ] **Step 8: Commit**

```bash
git add theme-src docs/theme tools/check_docs_site.py
git commit -m "[misc] style docs content: prose, code, admonitions, tables, tabs"
```

---

### Task 5: Search

**Files:**
- Create: `docs/theme/assets/vendor/lunr.min.js`
- Create: `docs/theme/assets/js/search.js`
- Modify: `docs/theme/partials/search.html` (new file), `docs/theme/partials/header.html`, `docs/theme/assets/theme.js`, `theme-src/app.css`, `tools/check_docs_site.py`

**Interfaces:**
- Consumes: the header markup from Task 3.
- Produces: `initSearch()` exported from `js/search.js`; a `<dialog data-search>` in the page; results link to `<location>?h=<query>` and the same module highlights those terms on load.

- [ ] **Step 1: Add the assertions**

```python
@check("the search dialog and engine ship with the site")
def _search_ui():
    html = read(MODULE_PAGE)
    if "data-search" not in html:
        return "no search dialog in the page"
    if not (SITE / "theme" / "assets" / "vendor" / "lunr.min.js").exists():
        return "lunr.min.js was not copied into the site"
```

- [ ] **Step 2: Run the checker — it must fail**

Expected: 1 failure, 11 passes.

- [ ] **Step 3: Vendor lunr**

```bash
mkdir -p docs/theme/assets/vendor
curl -fsSL https://unpkg.com/lunr@2.3.9/lunr.min.js \
  -o docs/theme/assets/vendor/lunr.min.js
head -c 100 docs/theme/assets/vendor/lunr.min.js
```

Expected: the lunr banner comment naming version 2.3.9. Record that version in a comment at the top of `search.js`.

- [ ] **Step 4: Write the search module**

`docs/theme/assets/js/search.js`:

```js
// Site search over the index the MkDocs `search` plugin emits at
// search/search_index.json. Engine: lunr 2.3.9, vendored in assets/vendor/.
//
// The plugin writes one record per page AND one per section with its anchor,
// so results land on the right heading. The index is ~500 KB raw, so it is
// fetched on first use, never on page load.
let indexPromise = null;

async function loadIndex(base) {
  const response = await fetch(`${base}search/search_index.json`);
  const payload = await response.json();
  const documents = new Map();

  const index = lunr(function () {
    this.ref("location");
    this.field("title", { boost: 10 });
    this.field("text");
    for (const doc of payload.docs) {
      documents.set(doc.location, doc);
      this.add(doc);
    }
  });

  return { index, documents };
}

function moduleOf(location) {
  const [first] = location.split("/");
  return first && !first.includes(".") ? first : "Home";
}

function snippet(text, terms) {
  const lowered = text.toLowerCase();
  const at = terms
    .map((term) => lowered.indexOf(term.toLowerCase()))
    .filter((position) => position >= 0)
    .sort((a, b) => a - b)[0];
  const start = Math.max(0, (at ?? 0) - 60);
  const raw = text.slice(start, start + 200);
  const escaped = raw.replace(/[&<>]/g, (c) => `&#${c.charCodeAt(0)};`);
  return terms.reduce(
    (acc, term) =>
      acc.replace(new RegExp(`(${term})`, "gi"), "<mark>$1</mark>"),
    escaped,
  );
}

export function initSearch() {
  const dialog = document.querySelector("[data-search]");
  const input = dialog?.querySelector("[data-search-input]");
  const output = dialog?.querySelector("[data-search-results]");
  const opener = document.querySelector("[data-search-open]");
  if (!dialog || !input || !output || !opener) return;

  const base = document.documentElement.dataset.base || "";

  const open = () => {
    dialog.showModal();
    input.focus();
    if (!indexPromise) {
      output.innerHTML = "<li class='docs-search__status'>Indexing…</li>";
      indexPromise = loadIndex(base);
    }
  };

  opener.addEventListener("click", open);
  document.addEventListener("keydown", (event) => {
    const typing = /^(INPUT|TEXTAREA)$/.test(event.target.tagName);
    if (typing) return;
    if (event.key === "/" || (event.key.toLowerCase() === "k" && (event.metaKey || event.ctrlKey))) {
      event.preventDefault();
      open();
    }
  });

  input.addEventListener("input", async () => {
    const query = input.value.trim();
    if (query.length < 2) {
      output.innerHTML = "";
      return;
    }
    const { index, documents } = await indexPromise;
    const terms = query.split(/\s+/);
    const hits = index.query((q) => {
      for (const term of terms) {
        q.term(term, { boost: 2 });
        q.term(term, { wildcard: lunr.Query.wildcard.TRAILING });
      }
    });

    output.innerHTML =
      hits
        .slice(0, 20)
        .map((hit) => {
          const doc = documents.get(hit.ref);
          const href = `${base}${doc.location}?h=${encodeURIComponent(query)}`;
          return `<li class="docs-search__hit">
            <a href="${href}">
              <span class="docs-search__module">${moduleOf(doc.location)}</span>
              <span class="docs-search__title">${doc.title}</span>
              <span class="docs-search__text">${snippet(doc.text, terms)}</span>
            </a>
          </li>`;
        })
        .join("") || "<li class='docs-search__status'>No results</li>";
  });

  // Keyboard navigation across the result list.
  input.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowDown") return;
    event.preventDefault();
    output.querySelector("a")?.focus();
  });
}

// Highlights the terms carried over from the search dialog (?h=...).
export function highlightQuery() {
  const query = new URLSearchParams(location.search).get("h");
  const main = document.getElementById("docs-main");
  if (!query || !main || !window.CSS?.highlights) return;

  const ranges = [];
  const walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT);
  const needles = query.toLowerCase().split(/\s+/).filter(Boolean);

  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const text = node.textContent.toLowerCase();
    for (const needle of needles) {
      let from = text.indexOf(needle);
      while (from >= 0) {
        const range = new Range();
        range.setStart(node, from);
        range.setEnd(node, from + needle.length);
        ranges.push(range);
        from = text.indexOf(needle, from + needle.length);
      }
    }
  }

  CSS.highlights.set("search", new Highlight(...ranges));
}
```

- [ ] **Step 5: Add the dialog and the header entry point**

Create `docs/theme/partials/search.html`:

```html
<dialog class="docs-search" data-search aria-label="Search">
  <form method="dialog" class="docs-search__form">
    <input class="docs-search__input" data-search-input type="search"
           placeholder="Search the documentation" autocomplete="off">
    <button class="docs-search__close" value="close" aria-label="Close">×</button>
  </form>
  <ul class="docs-search__results" data-search-results></ul>
</dialog>
```

In `docs/theme/partials/header.html`, put a search button before the scheme toggle:

```html
  <button class="docs-header__search" type="button" data-search-open>
    Search <kbd>/</kbd>
  </button>
```

In `docs/theme/base.html`: include `partials/search.html` just before the footer include, load lunr before the theme module, and expose the site base URL for `search.js`:

```html
    <script src="{{ 'theme/assets/vendor/lunr.min.js' | url }}"></script>
```

and on the `<html>` tag: `data-base="{{ '' | url }}"`.

Wire `initSearch()` and `highlightQuery()` into `theme.js`, and style `mark` plus the `::highlight(search)` pseudo-element in `theme-src/app.css`:

```css
  .prose mark,
  ::highlight(search) {
    background-color: var(--color-au-signal-faint);
    color: inherit;
  }
```

- [ ] **Step 6: Build and check**

```bash
npm run build:css && .venv-docs/bin/mkdocs build --strict && python3 tools/check_docs_site.py
```

Expected: `OK: 12 checks passed`.

- [ ] **Step 7: Exercise the search by hand**

Serve the site, then: press `/` — the dialog opens and shows `Indexing…` once; type `webhook` — results appear, each naming its module; press `ArrowDown` then `Enter` — the page opens at the right heading with the term highlighted; press `Esc` — the dialog closes. Confirm from DevTools' Network tab that `search_index.json` is fetched only on first open.

- [ ] **Step 8: Commit**

```bash
git add docs/theme theme-src/app.css tools/check_docs_site.py
git commit -m "[misc] add search to the docs theme on a vendored lunr"
```

---

### Task 6: Home page components

**Files:**
- Modify: `theme-src/app.css` (absorb `docs/stylesheets/module-table.css`)
- Modify: `docs/index.md` (two class names)
- Modify: `mkdocs.yml` if `extra_css` still lists the old stylesheet
- Modify: `tools/check_docs_site.py`

**Interfaces:**
- Consumes: the token layer from Task 2.
- Produces: `.mod-*`, `.hero-*` component classes with their existing names, and `.docs-button` / `.docs-button--primary` replacing `md-button`.

- [ ] **Step 1: Add the assertion**

```python
@check("the home page keeps its component class names")
def _home_components():
    html = read(HOME)
    for cls in ("hero-art", "mod-grid", "mod-tile", "docs-button"):
        if cls not in html:
            return f"{cls} missing from the home page"
    if "md-button" in html:
        return "md-button still present on the home page"
```

- [ ] **Step 2: Run the checker — it must fail**

Expected: 1 failure, 12 passes.

- [ ] **Step 3: Move the component CSS**

Copy the whole of `docs/stylesheets/module-table.css` into `theme-src/app.css` inside `@layer components`, changing only what referenced Material:

- `var(--md-default-fg-color--light)` → `var(--au-muted)`
- `var(--md-default-fg-color--lighter)` → `var(--au-faint)`
- `var(--md-default-fg-color--lightest)` → `var(--au-border)`
- `var(--md-default-fg-color)` → `var(--au-ink)`
- `var(--md-code-bg-color)` → `var(--au-panel)`
- `var(--au-*)` references stay as they are — those tokens still exist.

Do **not** rename any class. Keep every explanatory comment, including the cursor rationale on `.hero-art img.hero-art__zoomable` and `.hero-zoom__img`.

Then delete `docs/stylesheets/module-table.css` and drop the now-empty `extra_css` from `mkdocs.yml` if it is still there.

- [ ] **Step 4: Add the button component**

Append to `@layer components` in `theme-src/app.css`:

```css
  .docs-button {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.5rem 1rem;
    border: 1px solid var(--au-border-strong);
    border-radius: 999px;
    color: var(--au-ink);
    font-size: 0.86rem;
    font-weight: 500;
    text-decoration: none;
    transition: border-color 150ms ease, color 150ms ease;
  }

  .docs-button:hover { border-color: var(--au-border-hover); }

  /* The one gradient, as the primary call to action. */
  .docs-button--primary {
    border-color: transparent;
    background: var(--au-gradient);
    color: var(--color-au-primary-ink);
    font-weight: 600;
  }
```

- [ ] **Step 5: Update `docs/index.md`**

In the `hero-actions` block only, replace:

```html
      <a class="md-button md-button--primary" href="Core/admin/installation/">Installation</a>
      <a class="md-button" href="changelog/">Changelog</a>
      <a class="md-button" href="https://github.com/oduist/connect_addons_ng" target="_blank" rel="noopener">View on GitHub</a>
```

with the same three links carrying `docs-button` / `docs-button docs-button--primary`. Nothing else in the file changes.

- [ ] **Step 6: Build and check**

```bash
npm run build:css && .venv-docs/bin/mkdocs build --strict && python3 tools/check_docs_site.py
```

Expected: `OK: 13 checks passed`.

- [ ] **Step 7: Compare the home page against the baseline**

Screenshot `/` in both schemes at 1280px and at 390px. Compare with `/tmp/docs-baseline/home-*.png`: the periodic table, the legend filter (click a category — squares outside it must dim), the hero screenshot lightbox (click to enlarge, magnifier hint on hover, plain arrow cursor over the image, close button, `Esc`). All of this is driven by the untouched `module-table.js` / `hero-zoom.js`, so any breakage here is a CSS-name mismatch.

- [ ] **Step 8: Commit**

```bash
git add theme-src/app.css docs/index.md docs/stylesheets mkdocs.yml tools/check_docs_site.py
git commit -m "[misc] move the home page components into the docs theme"
```

---

### Task 7: Footer, prev/next and Edit on GitHub

**Files:**
- Modify: `docs/theme/partials/footer.html`, `docs/theme/partials/header.html`, `mkdocs.yml`, `theme-src/app.css`, `tools/check_docs_site.py`

**Interfaces:**
- Consumes: the header and footer include points from Tasks 2–3.
- Produces: `page.edit_url`-driven link; footer navigation from `page.previous_page` / `page.next_page`.

- [ ] **Step 1: Add the assertions**

```python
@check("the footer offers prev/next navigation")
def _prev_next():
    html = read(MODULE_PAGE)
    if 'class="docs-pager"' not in html:
        return "no pager in the footer of a module page"


@check("edit links point at the owning module's source file")
def _edit_url():
    html = read(MODULE_PAGE)
    match = re.search(r'href="([^"]*edit/19\.0/[^"]+)"', html)
    if not match:
        return "no Edit on GitHub link on a module page"
    url = match.group(1)
    # mkdocs-monorepo-plugin must rewrite this back to the module's own docs/
    # folder; an unrewritten URL would point at the aggregated temp path.
    if "connect_twilio/docs/configuration.md" not in url:
        return f"edit link points at {url}, not the module source"
```

- [ ] **Step 2: Run the checker — both must fail**

Expected: 2 failures, 13 passes.

- [ ] **Step 3: Configure the repository in `mkdocs.yml`**

Add, next to `site_url`:

```yaml
# Drives the "Edit on GitHub" link. Aggregated pages live in a temporary
# docs_dir, so a naive edit_url would point at a path that does not exist in
# the repository; mkdocs-monorepo-plugin rewrites it back to the owning module
# (mkdocs_monorepo_plugin/edit_uri.py).
repo_url: https://github.com/oduist/connect_addons_ng
edit_uri: edit/19.0/
```

- [ ] **Step 4: Write the footer**

`docs/theme/partials/footer.html`:

```html
<footer class="docs-footer">
  {% if page and (page.previous_page or page.next_page) %}
    <nav class="docs-pager" aria-label="Page navigation">
      {% if page.previous_page %}
        <a class="docs-pager__link" href="{{ page.previous_page.url | url }}">
          <span class="docs-pager__label">Previous</span>
          <span>{{ page.previous_page.title }}</span>
        </a>
      {% endif %}
      {% if page.next_page %}
        <a class="docs-pager__link docs-pager__link--next"
           href="{{ page.next_page.url | url }}">
          <span class="docs-pager__label">Next</span>
          <span>{{ page.next_page.title }}</span>
        </a>
      {% endif %}
    </nav>
  {% endif %}

  <div class="docs-footer__meta">
    <span>{{ config.copyright }}</span>
    {% if page and page.edit_url %}
      <a href="{{ page.edit_url }}" rel="noopener" target="_blank">Edit on GitHub</a>
    {% endif %}
  </div>
</footer>
```

- [ ] **Step 5: Add the repository link to the header**

In `docs/theme/partials/header.html`, between the search button and the scheme toggle:

```html
  {% if config.repo_url %}
    <a class="docs-header__repo" href="{{ config.repo_url }}" rel="noopener"
       target="_blank">GitHub</a>
  {% endif %}
```

- [ ] **Step 6: Style the footer**

Append to `@layer components`:

```css
  .docs-footer {
    max-width: 84rem;
    margin-inline: auto;
    padding: 2rem 1.5rem 3rem;
    border-top: 1px solid var(--au-border);
    color: var(--au-muted);
    font-size: 0.82rem;
  }

  .docs-pager { display: flex; justify-content: space-between; gap: 1rem; }

  .docs-pager__link {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    padding: 0.7rem 1rem;
    border: 1px solid var(--au-border);
    border-radius: var(--radius-au-md);
    color: var(--au-ink);
    text-decoration: none;
  }

  .docs-pager__link--next { margin-left: auto; text-align: right; }
  .docs-pager__link:hover { border-color: var(--au-border-hover); }
  .docs-pager__label { color: var(--au-faint); font-size: 0.72rem; }

  .docs-footer__meta {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    margin-top: 1.6rem;
  }
```

- [ ] **Step 7: Build and check**

```bash
npm run build:css && .venv-docs/bin/mkdocs build --strict && python3 tools/check_docs_site.py
```

Expected: `OK: 15 checks passed`. If the edit-link assertion fails on the path shape, open the built page and read the actual URL before adjusting — the assertion encodes what the monorepo plugin is supposed to do, so a mismatch is a real finding, not a test to loosen.

- [ ] **Step 8: Follow the link**

Open the Edit on GitHub link from `/Twilio/configuration/` in a browser: it must land on GitHub's editor for `connect_twilio/docs/configuration.md` on branch `19.0`.

- [ ] **Step 9: Commit**

```bash
git add docs/theme mkdocs.yml theme-src/app.css tools/check_docs_site.py
git commit -m "[misc] add pager, edit link and repo link to the docs theme"
```

---

### Task 8: Remove Material, wire CI, update the docs about the docs

**Files:**
- Delete: `docs/stylesheets/aurora.css`, `docs/overrides/` (whole directory)
- Modify: `docs/requirements.txt`, `.github/workflows/docs.yml`, `AGENTS.md`, `specs/docs_site.md`
- Create: `docs/README.md`
- Modify: `tools/check_docs_site.py`

**Interfaces:**
- Consumes: everything above.
- Produces: a build that no longer imports Material anywhere.

- [ ] **Step 1: Add the assertion**

```python
@check("the build no longer depends on Material")
def _material_gone():
    requirements = pathlib.Path("docs/requirements.txt").read_text()
    if "mkdocs-material" in requirements:
        return "mkdocs-material is still a documented dependency"
    if pathlib.Path("docs/overrides").exists():
        return "docs/overrides/ still exists"
    if pathlib.Path("docs/stylesheets/aurora.css").exists():
        return "docs/stylesheets/aurora.css still exists"
```

- [ ] **Step 2: Run the checker — it must fail**

Expected: 1 failure, 15 passes.

- [ ] **Step 3: Delete what Material needed**

```bash
git rm -r docs/overrides
git rm docs/stylesheets/aurora.css
rmdir docs/stylesheets 2>/dev/null || true
```

- [ ] **Step 4: Rewrite `docs/requirements.txt`**

```
# Documentation build dependencies.
# The site ships its own theme (docs/theme/, specs/docs_site.md); the CSS is
# built with the Tailwind CLI from package.json and committed, so a
# Markdown-only contributor needs nothing but these.
mkdocs==1.6.1

# Aggregates each module's docs/ folder into one site (see root mkdocs.yml).
mkdocs-monorepo-plugin==1.1.2
```

Pin `mkdocs` to whatever `.venv-docs/bin/mkdocs --version` currently reports — Material used to pull it in transitively, so it was never pinned here.

- [ ] **Step 5: Rebuild from a clean environment**

```bash
python3 -m venv /tmp/venv-docs-check
/tmp/venv-docs-check/bin/pip install -r docs/requirements.txt
/tmp/venv-docs-check/bin/mkdocs build --strict
python3 tools/check_docs_site.py
```

Expected: a clean build with no Material installed anywhere, and `OK: 16 checks passed`. This is the real proof the dependency is gone.

- [ ] **Step 6: Add the CSS build to CI**

In `.github/workflows/docs.yml`, after the Python setup and before the deploy step:

```yaml
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm

      - name: Build the theme stylesheet
        run: npm ci && npm run build:css

      # The compiled stylesheet is committed so that `mkdocs serve` works
      # without Node. Fail loudly if the committed copy is stale.
      - name: Verify the committed stylesheet is current
        run: git diff --exit-code docs/theme/assets/app.css
```

Extend the workflow's `paths:` filter with `theme-src/**`, `package.json` and `package-lock.json`, and add a build check step:

```yaml
      - name: Check the built site
        run: python3 tools/check_docs_site.py site
```

Note the checker runs against `site/`, so it needs `mkdocs build` before `gh-deploy`, or move the check after the deploy step using the directory `gh-deploy` leaves behind. Prefer an explicit `mkdocs build` before deploying.

- [ ] **Step 7: Write `docs/README.md`**

```markdown
# Documentation site

Built with MkDocs and an in-repo theme (`docs/theme/`, spec: `specs/docs_site.md`).

## Editing pages only

Module documentation lives in each module's own `docs/` folder and is
aggregated by `mkdocs-monorepo-plugin`. To preview:

    pip install -r docs/requirements.txt
    mkdocs serve

The theme's stylesheet is committed, so this needs no Node.

## Changing the theme

    npm install
    npm run dev        # tailwind --watch alongside mkdocs serve

Before committing a theme change, rebuild the stylesheet and commit it:

    npm run build:css
    git add docs/theme/assets/app.css

CI fails if the committed file differs from a fresh build.
```

- [ ] **Step 8: Update the repo's own guidance**

In `AGENTS.md`, in Key Files, change the docs line to name the new setup and the spec:

```
- `docs/` — User and admin documentation (MkDocs + the in-repo Aurora theme, see `specs/docs_site.md`)
```

In `specs/docs_site.md`, update the File Layout section so it lists `docs/theme/assets/js/` with the five modules (`scheme.js`, `toc.js`, `drawer.js`, `copy.js`, `search.js`) plus `theme.js` as the entry point, matching what was actually built.

- [ ] **Step 9: Full verification**

```bash
npm run build:css && git diff --exit-code docs/theme/assets/app.css
.venv-docs/bin/mkdocs build --strict && python3 tools/check_docs_site.py
```

Expected: no diff, clean strict build, all checks pass.

- [ ] **Step 10: Commit**

```bash
git add -A docs specs AGENTS.md .github/workflows/docs.yml tools/check_docs_site.py
git commit -m "[misc] drop mkdocs-material and build the theme css in ci"
```

---

### Task 9: Visual parity review

The checker proves structure; this task proves appearance. Nothing ships until this passes.

**Files:**
- Modify: whatever the comparison turns up (expected: `theme-src/app.css`)

**Interfaces:**
- Consumes: `/tmp/docs-baseline/*.png` from Task 1.

- [ ] **Step 1: Capture the after-shots**

Serve the built site and capture exactly the same set as Task 1 Step 2, into `/tmp/docs-after/`, same viewports, same schemes.

- [ ] **Step 2: Compare page by page**

`Read` each before/after pair and note every difference. Expected-and-fine: font rendering nudges, a few pixels of spacing. Not fine: different colours, missing gradients, changed type scale, tables or code blocks that now overflow, admonition accents that swapped meaning.

- [ ] **Step 3: Walk the interaction checklist**

- [ ] Search: `/` and `⌘K` open it; typing yields results; `ArrowDown` + `Enter` navigates; the target term is highlighted on arrival; `Esc` closes
- [ ] Scheme toggle: switches, persists across a reload, and the page never flashes the wrong palette on load
- [ ] Sidebar: on a Twilio page lists only Twilio; the current page is marked `aria-current`; sections expand
- [ ] Breadcrumbs: stay under the header while scrolling; every crumb navigates; a deep link lands below the trail, not under it
- [ ] TOC: the highlight follows the scroll position
- [ ] Code: the copy button appears on hover and copies
- [ ] Pager: previous/next resolve to the neighbouring pages
- [ ] Edit on GitHub: opens the module's own source file
- [ ] 390px: the burger opens the drawer, `Esc` closes it, focus is trapped while open, nothing scrolls horizontally
- [ ] Home: category filter dims other squares; the hero lightbox opens, shows a plain arrow cursor over the image, and closes

- [ ] **Step 4: Fix and re-verify**

Fix whatever the comparison found, rebuild the CSS, re-run the checker, re-capture the affected screenshots.

- [ ] **Step 5: Commit and open the PR**

```bash
git add -A
git commit -m "[misc] match the tailwind theme to the reference screenshots"
git push -u origin 19.0-docs-tailwind-theme
gh pr create --base 19.0 --title "[misc] replace mkdocs-material with an in-repo tailwind theme" --body "..."
```

The PR body should link `specs/decisions/050-docs-custom-tailwind-theme.md` and state plainly that the site is meant to look unchanged, so reviewers know that any visual difference is a bug rather than the point.

---

## Self-Review Notes

Spec coverage checked section by section: file layout (Tasks 2, 8), `mkdocs.yml` changes (Tasks 2, 6, 7), every template in the spec (Tasks 2, 3, 5, 7), tokens and both schemes (Task 2), prose/code/admonitions/tables/tabs (Task 4), home-page components (Task 6), search (Task 5), build and the committed stylesheet (Tasks 1, 8), migration order (Tasks 2–8 follow the spec's seven steps), verification (Tasks 1, 9), non-goals (nothing in the plan touches them).

Two deliberate deviations from the spec, both recorded above: `theme.js` is split into per-behaviour modules (Task 8 Step 8 updates the spec), and the light scheme's neutral tokens are newly authored because the current site inherits them from Material rather than declaring them (Task 2 Step 3 flags this for verification against the reference screenshots).
