# How the Book Finds Documentation

`connect_book` serves this documentation inside Odoo. It has no configuration
and no settings page: install it, and the **Connect ▸ Documentation** menu
appears. What follows is the contract it reads, so that a module you write or
change shows up in the Book the way you expect.

## One source, two readers

Documentation lives in each module's own `docs/` folder. Two things read it:

| Reader | What it produces |
|--------|------------------|
| MkDocs (root `mkdocs.yml`, `mkdocs-monorepo-plugin`) | the public documentation site |
| `connect.book` (this module) | the User Guide and Admin Guide inside Odoo |

There is no second copy of the documentation for the Book, and no export step.
Both readers open the same Markdown files, and both take their page titles and
page order from the same per-module `mkdocs.yml`.

!!! info "Only installed modules"
    The Book lists the modules whose name starts with `connect` **and** whose
    state is `installed`. A module present on disk but not installed on this
    database contributes nothing.

## What a module must ship

Two things, both of which it already needs for the documentation site:

1. `<module>/mkdocs.yml` with a `site_name` and a `nav`.
2. `<module>/docs/<page>.md` for every page the `nav` lists.

`site_name` is the name shown above the module's pages in the Book's table of
contents; the module's technical name is the fallback if it is missing.

A module with no `mkdocs.yml`, or whose `nav` lists no readable page for an
audience, simply does not appear in that book.

## Which book a page lands in

Every page belongs to exactly one audience. The rule is applied in this order,
first match wins:

1. **The `nav` section.** A top-level section named `Admin Guide` or
   `User Guide` sets the audience of every page under it. This is the explicit
   form and it overrides everything else.
2. **The path prefix.** A page under `docs/admin/` is administrator
   documentation; a page under `docs/user/` is user documentation.
3. **The default: administrator.** A page that declares neither — a flat
   `index.md`, `configuration.md` — is treated as administrator documentation.

The default errs on the side of the narrower audience: a page never becomes
readable to more people because someone forgot to classify it.

=== "Explicit sections"
    ```yaml
    site_name: Core
    nav:
      - Admin Guide:
          - Installation: admin/installation.md
      - User Guide:
          - Getting Started: user/getting-started.md
    ```

=== "Path prefixes"
    ```yaml
    site_name: FreeSWITCH
    nav:
      - SIP Firewall: admin/firewall.md
      - Call Parking: user/parking.md
    ```

!!! tip "Writing a page for end users"
    Put it under `docs/user/`, or list it under a `User Guide:` section. Those
    are the only two ways a page reaches someone who is not a Connect
    administrator.

## Cross-references between pages

Pages link to each other by file name, the way MkDocs expects:
`[Security](security.md)`, `[Firewall](admin/firewall.md#troubleshooting)`. The
site resolves those into URLs; the Book resolves them into page jumps within
the right-hand pane.

A link that resolves outside the module's `docs/` folder is rendered inert
rather than followed, and a link to a page the reader's book does not hold does
nothing. Links to external addresses are left untouched and open in a new tab.

## Markdown support

The Book renders Markdown itself, with no third-party package, so it works in
any Odoo image. It covers headings, paragraphs, nested lists, fenced code,
blockquotes, tables, horizontal rules and inline formatting, plus the two
MkDocs constructs this repository uses:

- **Admonitions** — `!!! note "Title"` and the `info`, `tip`, `warning`,
  `danger`, `example` kinds, with a four-space-indented body.
- **Content tabs** — `=== "Label"` blocks. The site renders them as a
  switcher; the Book stacks them as labelled panels, so every variant stays
  readable.

Anything outside that subset degrades to plain text rather than breaking the
page. A page's YAML front matter is stripped before rendering — it configures
the site, not the Book.

!!! warning "One oversized page is skipped, not truncated"
    A Markdown file larger than 1 MB is left out of the book, with a warning in
    the server log. A page that fails to render is dropped the same way, so a
    single bad file never takes the whole book down with it.

## Access

| Menu | Group required |
|------|----------------|
| Connect ▸ Documentation ▸ User Guide | **Connect / User** (`connect.group_user`) |
| Connect ▸ Documentation ▸ Admin Guide | **Connect / Admin** (`connect.group_admin`) |

The menus are hidden from anyone without the group, and the model checks the
group again on every call — a hidden menu is a convenience, not the access
control. `connect.group_admin` implies `connect.group_user`, so an
administrator sees both books.

`connect.book` is an abstract model: it stores nothing and has no table, so
there are no access rules to grant on it.

## Translations

A translated page lives at `docs/i18n/<lang>/<same relative path>` — for
example `docs/i18n/fr/user/getting-started.md` mirrors
`docs/user/getting-started.md`. The Book prefers the translation matching the
reader's Odoo language and falls back to the source page when there is none, so
a partially translated module is served page by page rather than all-or-nothing.

Only the short language tag is used: `fr_BE` reads `docs/i18n/fr/`.

## Performance

Rendered pages are cached per worker, keyed by file path and modification time,
as are the parsed `mkdocs.yml` files. Editing a file invalidates its entry on
the next read, so a redeploy needs no cache flush and no server restart to show
new documentation — only an Odoo module upgrade if the module itself is new.
