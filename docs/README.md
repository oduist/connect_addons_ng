# Documentation site

Built with MkDocs. The look comes from the **Aurora** theme, which lives in its
own repository and installs from `docs/requirements.txt`; this repository holds
the content, the navigation and the home page's own components.

## Editing pages

Module documentation lives in each module's own `docs/` folder and is
aggregated by `mkdocs-monorepo-plugin`. To preview:

    pip install -r docs/requirements.txt
    mkdocs serve

That is the whole toolchain — no Node, no build step. The theme arrives with its
stylesheet already compiled.

## Changing how the site looks

Where a change belongs depends on what it touches:

- **The home page** — its hero, the screenshot lightbox and the module table —
  is this repository's own. Styles: `docs/stylesheets/home.css` (plain CSS).
  Markup: `docs/index.md`. Behaviour: `docs/javascripts/`.
- **Everything else** — page skeleton, header, navigation, typography, search,
  footer, colour tokens — belongs to the theme. Clone the theme repository,
  install it here in editable mode (`pip install -e /path/to/mkdocs-theme-aurora`)
  and work there; when the change ships, bump the pin in
  `docs/requirements.txt`.

## Checking the built site

    mkdocs build --strict
    python3 tools/check_docs_site.py

The checker asserts what a successful build does not: that the sidebar stays
scoped to one module, that breadcrumbs walk back to Home, that the edit link
resolves to a module's own source file, and that the type scale has not
drifted. CI runs both on every pull request that touches the docs.
