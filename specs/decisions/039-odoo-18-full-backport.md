# ADR-039: Full Odoo 19 to Odoo 18 backport

## Status

Accepted.

## Context

The Odoo 18 branch contains earlier, individually backported changes, while
Odoo 19 has since accumulated provider separation, new telephony providers,
co-located tests, working schedules, website snippets, and security fixes.
Replaying every Odoo 19 commit would repeat already ported work, create noisy
conflicts, and produce intermediate manifest versions that do not represent a
release boundary.

Python source must remain byte-identical between Odoo 18 and Odoo 19. Odoo
version differences therefore belong in shared `release.version_info` branches.
Only version-specific assets and migration entry points may differ.

## Decision

Backport the final Odoo 19 tree as a single release-oriented synchronization,
using commit `e678ed0ad5984b5c3739e4cb3f05660a8417a547` as the source baseline and
including the cross-series `res.groups` test compatibility change delivered
with this ADR. The resulting source snapshot commit is recorded in the Odoo 18
backport pull request.

The Odoo 18 port will:

- preserve Python files byte-for-byte, apart from manifest series prefixes and
  per-series migration entry points;
- keep product-version tails aligned and bump each manifest at most once;
- retain Odoo 18 migration history and add only entry points required from the
  currently released Odoo 18 versions to the synchronized versions;
- adapt group XML, unsupported view widgets, Owl validation, and website
  builder/runtime JavaScript to Odoo 18 APIs without changing public behavior;
- validate both database upgrades and clean installation of the new provider
  modules on Odoo 18 before opening the backport pull request.

## Consequences

The Odoo 18 pull request is intentionally large but represents one auditable
product-state transition. Review can compare Python directly with the recorded
Odoo 19 snapshot, while the remaining review focuses on manifests, migrations,
and Odoo 18-specific frontend assets.
