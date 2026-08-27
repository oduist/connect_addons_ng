# Connect Book Module Specification

## Module Info

- **Name:** Oduist Connect Book
- **Technical:** `connect_book`
- **Version:** 19.0.1.0.0
- **Depends:** `connect`, `web`
- **Application:** False
- **Auto-install:** False
- **License:** Other proprietary

## Overview

`connect_book` serves this repository's documentation inside Odoo. It crawls
every **installed** module whose name starts with `connect`, reads the Markdown
pages from that module's own `docs/` folder, and assembles them into two client
actions: the **User Guide** and the **Admin Guide**.

The documentation it reads is the documentation the site is built from — the
same files, the same titles, the same order. There is no second tree and no
export step (ADR-059).

Responsibilities:

- Discover documentation pages through each module's `mkdocs.yml` `nav`
- Classify every page as user or administrator documentation
- Render Markdown to HTML without a third-party dependency
- Serve translated pages when a mirror exists, the source page otherwise
- Enforce the reading group server-side on every call

Non-responsibilities: it has **no settings**, stores **nothing**, writes
nothing to the database, and does not register in `ODUIST_MODULES` (there is
no per-module license behavior to gate).

---

## Models (connect_book/models/)

### 1. connect_book.py — `connect.book` (`models.AbstractModel`)

Abstract by design: the Book is a read path over the filesystem, so there is no
table, no records and no `ir.model.access` rows to grant.

**Module-level constants:**

| Constant | Value | Purpose |
|----------|-------|---------|
| `DOCS_DIRNAME` | `"docs"` | The folder holding a module's pages |
| `MKDOCS_FILENAME` | `"mkdocs.yml"` | Per-module config carrying `site_name` + `nav` |
| `I18N_DIRNAME` | `"i18n"` | Translated mirrors under `docs/i18n/<lang>/` |
| `MODULE_PREFIX` | `"connect"` | Only `connect*` modules are crawled |
| `USER_GROUP` | `connect.group_user` | Required for the User Guide |
| `ADMIN_GROUP` | `connect.group_admin` | Required for the Admin Guide |
| `MAX_DOC_BYTES` | `1048576` | A larger page is skipped, with a log warning |
| `AUDIENCE_USER` / `AUDIENCE_ADMIN` | `"user"` / `"admin"` | The two books |
| `SECTION_AUDIENCE` | `{admin guide, user guide}` → audience | Explicit nav classification |
| `PREFIX_AUDIENCE` | `{admin, user}` → audience | Path-prefix classification |
| `DEFAULT_AUDIENCE` | `AUDIENCE_ADMIN` | Unclassified pages stay admin-only |

**Public methods (`@api.model`, called through the controller):**

| Method | Description |
|--------|-------------|
| `get_book()` | The User Guide. Raises `AccessError` without `connect.group_user`. Returns `{"modules": [...]}` |
| `get_admin_book()` | The Admin Guide. Raises `AccessError` without `connect.group_admin`. Same shape |

**Internal methods:**

| Method | Description |
|--------|-------------|
| `_doc_lang()` | Short language tag from context/user (`en_US` → `en`); anything not matching `LANG_CODE_RE` falls back to `en`, so a crafted `lang` cannot escape the docs folder |
| `_collect_modules(audience, lang)` | Searches installed `connect*` modules in name order and assembles their pages for one audience |
| `_read_nav(module_path)` | Reads and caches a module's `mkdocs.yml`; returns `(site_name, entries)` |
| `_parse_nav(lines)` | The hand-written nav parser (see below) |
| `_page_audience(relpath, section)` | Applies the classification rule |
| `_read_module_doc(module_path, relpath, lang)` | Translation-first read of one page |
| `_render_doc_html(filepath)` | Size guard, i18n-marker and front-matter strip, `md_to_html`, cache |
| `_rewrite_internal_links(html, module, relpath)` | Turns cross-page `.md` links into `data-book-page` ids |

**Return shape** (both books):

```python
{"modules": [
    {"id": "connect",              # technical module name
     "title": "Core",              # mkdocs site_name, else shortdesc, else id
     "pages": [
         {"id": "connect/user/calls.md",   # module name + nav path
          "title": "Making and Receiving Calls",
          "html": "<h1 …>…"},
     ]},
]}
```

A module with no `mkdocs.yml`, or with no readable page for the requested
audience, is omitted entirely.

**Caches** — two module-level dicts, per worker, keyed by file path and
invalidated on `st_mtime` change: `_RENDER_CACHE` (rendered HTML) and
`_NAV_CACHE` (parsed navs). A redeploy therefore needs no cache flush.

#### The nav contract

`mkdocs.yml` is parsed by a purpose-built parser rather than PyYAML: the nav
blocks are a fixed two-level shape and the Book must work in any Odoo image
without an extra dependency — the same reason Markdown is rendered by hand.

Recognised lines, inside the `nav:` block only, until the next column-0 key:

| Form | Meaning |
|------|---------|
| `  - Title: path.md` | A page. The title match is greedy, so a colon inside the title binds to the title |
| `  - Section:` | A section; entries indented below it inherit it |
| `# …`, blank | Ignored |

`path.md` must match `^[\w-]+(/[\w-]+)*\.md$`; anything else (a `..` segment, an
absolute path) is dropped, so a nav entry cannot read outside `docs/`.

#### Audience classification

First match wins:

1. a top-level nav section named `Admin Guide` or `User Guide`;
2. the first path segment: `docs/admin/…` or `docs/user/…`;
3. `DEFAULT_AUDIENCE` — administrator.

The default is deliberately the narrower audience: a page never becomes
readable to more people because nobody classified it.

#### Internal links

The renderer emits `<a href="…md" target="_blank" rel="noreferrer noopener">`
for a cross-page link. `_rewrite_internal_links` resolves it against the current
page's directory and replaces it with `<a href="#" data-book-page="<module>/<path>">`.
A target that normalises outside `docs/` becomes an inert `<a href="#">`.
External links are untouched.

### 2. markdown.py — `md_to_html(text)`

A dependency-free renderer. Everything is escaped first, so no raw markup from a
source file reaches the HTML, and only `http`, `https` and `mailto` survive as
link schemes (anything else becomes `#`).

Covers: headings (with `id` slugs), paragraphs, nested ordered/unordered lists,
fenced code (including a coloured `diff` lexer), blockquotes, tables, horizontal
rules, and inline bold/italic/code/link/image.

Plus the two MkDocs constructs this repository uses:

| Construct | Source | Rendered as |
|-----------|--------|-------------|
| Admonition | `!!! kind "Title"` + 4-space body | `div.o_book_admonition.o_book_admonition_<kind>` with a `p.o_book_admonition_title`; an unknown kind degrades to `note`, a missing title to the capitalised kind |
| Content tabs | consecutive `=== "Label"` blocks | one `div.o_book_tabs` holding a `div.o_book_tab` per label — stacked panels, not a switcher, because a documentation page carries no JavaScript |

Both bodies are rendered recursively as Markdown.

---

## Controllers (connect_book/controllers/main.py)

| Route | Type | Auth | Delegates to |
|-------|------|------|--------------|
| `/connect_book/book` | `jsonrpc` | `user` | `connect.book.get_book()` |
| `/connect_book/admin` | `jsonrpc` | `user` | `connect.book.get_admin_book()` |

Both are thin wrappers: the group check lives in the model, so it holds for any
caller, not just these routes.

---

## Frontend (connect_book/static/src/)

| File | Role |
|------|------|
| `book/book.js` | `BookApp` — the two-pane viewer, registered as the `connect_book.book` client action |
| `book/book.xml` | Its OWL template |
| `book/book.scss` | Styles for the shell, the rendered documentation, admonitions and tabs |
| `admin/adminbook.js` | `AdminBookApp extends BookApp` — same component, `static endpoint = "/connect_book/admin"`, registered as `connect_book.admin` |

`BookApp` holds `{modules, activeId, search, loaded}`. It opens the first page
of the first module, filters the contents by module name (keeping all its
pages) or by page title, and switches page on a click. `selectPage` ignores an
unknown id, so a cross-reference to a page this book does not hold leaves the
reader where they are rather than blanking the pane. `onContentClick` is
delegated on the content pane and acts only on `[data-book-page]`.

---

## Views (connect_book/views/connect_book_views.xml)

| Record | Notes |
|--------|-------|
| `action_connect_book` | `ir.actions.client`, tag `connect_book.book`, name "User Guide" |
| `action_connect_book_admin` | `ir.actions.client`, tag `connect_book.admin`, name "Admin Guide" |
| `menu_connect_documentation` | **Documentation** submenu under `connect.menu_connect_root`, sequence 90, `groups="connect.group_user"` — owned by this module, core has no such menu |
| `menu_connect_book_doc` | User Guide, sequence 5, `groups="connect.group_user"` |
| `menu_connect_book_admin` | Admin Guide, sequence 10, `groups="connect.group_admin"` |

---

## Security

No `ir.model.access` rows and no record rules: `connect.book` is abstract and
owns no table. Access is enforced twice — the menus are hidden without the
group, and each public method re-checks it, so the RPC endpoints are safe on
their own.

`connect.group_admin` implies `connect.group_user`, so a Connect administrator
reads both books.

---

## Translations

A translated page lives at `docs/i18n/<lang>/<same relative path>`. The read
path is translation-first, source-fallback, decided **per page**, so a
partially translated module is served page by page. A leading
`<!-- i18n … -->` provenance marker is stripped before rendering. Only the
short tag is used: `fr_BE` reads `docs/i18n/fr/`.

---

## Tests (connect_book/tests/)

| File | Covers |
|------|--------|
| `test_book.py` | Language normalisation and traversal rejection; nav parsing (flat, sectioned, prefixed, stop-at-next-key, escaping paths); translation-first reads, front-matter strip, size guard, render-failure isolation; link rewriting; the two group checks; the assembled page shape |
| `test_markdown.py` | The Markdown subset, escaping and URL-scheme neutralisation, list-kind switching, and the admonition/tab constructs |

The read path is exercised against a temporary module directory, with
`get_module_path` patched to point at it.

---

## Not ported from `connect_addons`

- **The Changes archive.** The source module collected
  `doc/changes/YYYY-MM-DD.md` per module into a day-by-day timeline. This
  repository keeps one Keep-a-Changelog file at `docs/changelog.md` instead, so
  the client action, its endpoint and the collector are left out rather than
  shipped reading nothing.
- **`doc/tech_spec.md`.** The technical layer lives in `specs/` here, and was
  deliberately hidden from the Book there too.
