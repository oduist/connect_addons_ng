---
name: writing-odoo-module-description
description: Use when writing or regenerating an Odoo module's Apps Store page (static/description/index.html) for an Oduist/connect addon — the store "description", app listing, module landing page, or features/marketing HTML shown in Odoo Apps and the Apps Store.
---

# Writing an Odoo Module Description

## Overview

The "description" of an Odoo module is its **Apps Store page**:
`static/description/index.html`. It is NOT free-form HTML — it follows a fixed
Oduist house style built on Odoo's `oe_*` / Bootstrap `alert` / Font Awesome
`fa` classes. Regenerating it means **filling a known template with content
extracted from the module's own code**, not inventing markup.

Do not confuse it with `doc/index.rst`, which is only a version **Change Log**.

## When to Use

- "Generate/write/regenerate the description for module X"
- A new addon under `connect_addons*` has no `static/description/index.html`
- Refreshing the features list after adding functionality

## Anatomy (fixed section order)

1. **Header** — `h2.oe_slogan` colored `#875A7B` (benefit slogan, ends `!`) +
   `h3.oe_slogan` (sub-slogan) + centered `icon.png`.
2. **Trial/pricing banner** (`alert alert-warning`) — only if the module is
   paid (`price` > 0 in manifest); delete for free modules.
3. **Features** — `h4.oe_slogan <b>Features</b>` + `alert alert-info` +
   `ul.list-unstyled`. Each `<li>` starts with `<i class="fa fa-check-square-o
   text-primary">` (delivered). The **last** `<li>` uses `fa-square-o` (empty
   box) for an upcoming feature or CTA.
4. **Documentation/Installation** (`alert alert-warning`) — "For documentation
   and support visit oduist.com".
5. **Check out more addons** (optional cross-sell panels).
6. **Footer** — verbatim `Oduist` / `Connecting Odoo to Everything!`.

Start from `template.html` in this skill directory — it has every section with
placeholders and inline rules.

## Procedure

1. **Read `__manifest__.py`.** Take `name`, `summary`, `price`, `category`,
   and `depends`.
   - If `depends` includes `connect` (and the module isn't `connect` itself),
     it is an **extension module** → make the first feature line
     "This is an extension module for the Connect application!".
   - `price` > 0 → keep the trial banner; `price: 0` → delete it.
2. **Derive the feature list from the code**, in user-facing terms — not model
   names. Scan:
   - `models/` — new business capabilities (a `connect.agent` model → "AI voice
     agents"; a recording field → "Call recording").
   - `views/` — buttons/actions the user sees (a "Call" button on a form →
     "One-click calling from the … form").
   - `controllers/` — webhooks/external endpoints exposed.
   - `data/` — shipped templates, crons, automated flows.
   Write 3–7 short benefit-oriented lines; keep the phrasing style of existing
   siblings (imperative, ends with `.` or `!`).
3. **Slogan + sub-slogan** from `summary`/`name`, phrased as a customer benefit.
4. **Fill `template.html`**, deleting sections that don't apply, and write it to
   `<module>/static/description/index.html`.
5. **Images & manifest wiring** (do NOT invent PNGs):
   - **`icon.png` is shared across ALL connect addons — present and future.**
     The canonical file is `connect/static/description/icon.png` (repo root).
     If the module's `static/description/icon.png` is missing, **copy the
     canonical one** into it; never fabricate or reuse a different icon:
     `cp connect/static/description/icon.png <module>/static/description/icon.png`
   - The manifest needs `logo.png` in `static/description/`. If missing, tell
     the user to add it (do not fabricate).
   - Ensure `__manifest__.py` has `'images': ['static/description/logo.png']`.

## Common Mistakes

- Writing Markdown or custom CSS instead of the `oe_*`/`alert`/`fa` house style.
- Listing model/technical names instead of user benefits.
- Making every feature `fa-check-square-o` — the last item is `fa-square-o`.
- Keeping the trial banner on a free (`price: 0`) module.
- Regenerating `doc/index.rst` (that's the changelog) when asked for the
  description.
- Using a per-module or fabricated `icon.png` — always copy the shared
  canonical `connect/static/description/icon.png`. Flag a missing `logo.png`.
