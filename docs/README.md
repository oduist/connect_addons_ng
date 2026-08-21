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
