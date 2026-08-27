# 059 — Connect Book reads the MkDocs tree

## Status

Accepted.

## Context

`connect_book` was written in `connect_addons`, where every module keeps a
flat `doc/` folder holding exactly three files — `user_guide.md`,
`admin_guide.md`, `tech_spec.md` — plus a `doc/changes/YYYY-MM-DD.md`
timeline. The model reads those file names directly, and the client action is a
one-page-per-module viewer.

`connect_addons_ng` has no such folder. Documentation here lives in
`<module>/docs/` as a tree of pages, listed and titled by a per-module
`mkdocs.yml`, and the root `mkdocs.yml` aggregates all of them into the public
documentation site through `mkdocs-monorepo-plugin` (ADR-050). Seventy-three
pages across twenty-six modules, written against `pymdownx` — admonitions,
content tabs — and cross-linking each other by relative `.md` file name.

Porting the module verbatim would therefore need a second documentation tree,
written and maintained in parallel with the one the site is built from.

## Options considered

**A. Port verbatim; write `doc/user_guide.md` and `doc/admin_guide.md` per
module.** Almost no code change. But it creates two documentation trees over
one product, with nothing keeping them in step. Everyone who edits a page has
to remember to edit its twin, and the day someone forgets, the Book and the
site disagree — with no test able to tell which one is right. Rejected.

**B. Migrate the repository to the flat `doc/` layout and drop MkDocs.** One
source of truth, and the module ports unchanged. But it throws away the
documentation site, its Aurora theme and its navigation, to spare a parser.
Rejected.

**C. Teach `connect.book` to read `<module>/docs/` and `<module>/mkdocs.yml`.**
One source, two readers: MkDocs builds the site, `connect.book` serves the same
files inside Odoo. Chosen.

## Decision

`connect.book` reads the documentation tree the site is built from.

- Pages come from `<module>/docs/`; their titles and order come from that
  module's `mkdocs.yml` `nav`, and the module's display name from its
  `site_name`. A module without a `mkdocs.yml` contributes nothing.
- `mkdocs.yml` is parsed by a small purpose-built parser, not by PyYAML. These
  nav blocks are a fixed two-level shape, and the Book must work in any Odoo
  image without an extra dependency — the same reason the module renders
  Markdown by hand rather than depending on a Markdown package.
- **Audience** — which of the two books a page lands in — is decided in this
  order: an explicit `Admin Guide` / `User Guide` `nav` section; else the
  `docs/admin/` or `docs/user/` path prefix; else administrator. The default is
  the narrower audience, so a page never becomes readable to more people
  because nobody classified it.
- The Markdown renderer gains the two MkDocs constructs the documentation
  actually uses: `!!!` admonitions and `=== "Label"` content tabs. Tabs render
  as stacked labelled panels — a documentation page carries no JavaScript, and
  in a manual every variant is worth reading anyway.
- Cross-page `.md` links are rewritten server-side into `data-book-page` page
  ids, which the client action turns into a jump within the viewer. A link
  resolving outside the module's `docs/` folder is rendered inert.

Two further departures from the source module:

- **Groups.** The source gated the Admin Guide on `base.group_system` and the
  User Guide on `connect.group_connect_user` / `group_connect_admin`, none of
  which exist here. This repository's roles are `connect.group_user` and
  `connect.group_admin` (the latter implies the former), so those are what the
  two books check. A Connect administrator, not an Odoo system administrator,
  is the person these admin pages are written for.
- **The Changes archive is not ported.** `doc/changes/YYYY-MM-DD.md` has no
  counterpart here; this repository keeps one Keep-a-Changelog file at
  `docs/changelog.md`. The client action, its endpoint and the per-day
  collector are left out rather than shipped reading nothing.

## Consequences

- Editing a documentation page updates the site and the Book at once. There is
  no export step and no second tree to keep in sync.
- The `nav` of a module's `mkdocs.yml` is now load-bearing beyond the site: it
  decides page titles, page order, and — through its section names — who may
  read a page. That contract is documented in
  `connect_book/docs/admin/book-setup.md`.
- With the audience rule applied to the tree as it stands, the User Guide is
  thin: the pages written for end users are `connect/docs/user/`, plus one each
  in FreeSWITCH, LiveKit and Customer Memory. Everything else is setup and
  configuration, correctly classified as administrator documentation. Widening
  the User Guide is a documentation task — move a page under `docs/user/` or
  list it in a `User Guide:` section — not a code change.
- The hand-written nav parser accepts the shape this repository uses. A module
  that reaches for a YAML feature outside it (anchors, multi-line scalars,
  quoted keys spanning lines) will parse as far as it can and silently skip the
  rest; the site would still build. Keeping module navs to the plain
  `- Title: path.md` form is therefore part of the contract.
