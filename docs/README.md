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

Everything visual belongs to the theme — the page skeleton, header, navigation,
typography, search and footer, and also the home page kit that `docs/index.md`
is written against (the hero, the buttons and the module table). Clone the theme
repository, install it here in editable mode
(`pip install -e /path/to/mkdocs-theme-aurora`) and work there; when the change
ships, bump the pin in `docs/requirements.txt`.

What stays here is what a page says: the Markdown, the navigation in
`mkdocs.yml`, and the hand-written HTML on the home page.

## Checking the built site

    mkdocs build --strict
    python3 tools/check_docs_site.py

The checker asserts what a successful build does not: that the sidebar stays
scoped to one module, that breadcrumbs walk back to Home, that the edit link
resolves to a module's own source file, and that the type scale has not
drifted. CI runs both on every pull request that touches the docs.
