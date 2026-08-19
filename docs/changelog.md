---
title: Changelog
hide:
  - navigation
---

# Changelog

All notable changes to Oduist Connect are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Module versions follow the Odoo convention `<series>.<product version>` — for
example `19.0.2.2.0` and `18.0.2.2.0` are the same product release on two Odoo
series, so entries below are written against the product version (`2.2.0`).

!!! note "Starting point"
    This file was introduced with the documentation site. Releases made before
    it are not listed retroactively — for the full history see the
    [commit log](https://github.com/oduist/connect_addons_ng/commits/19.0) on
    GitHub.

## [Unreleased]

### Added

### Changed

### Fixed

---

## How to add an entry

Add a bullet under **Unreleased** in the same pull request that makes the
change, then move the block under a new version heading when that version is
released.

- Write for the reader of the docs, not the reviewer of the diff: say what
  changed for an administrator or user, not which function was refactored.
- Name the module in bold when a change is provider-specific, e.g.
  **connect_telnyx**.
- Link to the page that documents the change where one exists.

```markdown
## [2.3.0] — 2026-09-01

### Added
- **connect_telnyx** — Call-failure notifications in the web phone, including a
  balance-blocked warning for administrators.
```
