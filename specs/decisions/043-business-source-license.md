# ADR-043: Business Source License 1.1 for all Connect modules

**Status:** Accepted
**Date:** 2026-07-17

## Context

Every Connect module already ships with `'license': 'Other proprietary'` in its
manifest, an `oduist.license` model (`connect/models/license.py`) that generates
a per-instance `instance_uid`, tracks a 30-day trial from module install date,
validates a per-instance JWT purchase token (RS256, `instance_hash` must match
`instance_uid`), and a systray license banner. Eight modules carried a bespoke
"Oduist Proprietary License v1.1" LICENSE file; six modules had no LICENSE file
at all.

The bespoke text was purely proprietary with no eventual open-source horizon,
its terms were not a recognised, well-understood license, and it was missing
from half the modules. We want a **source-available** posture that is:

- publicly downloadable and installable by anyone (source lives in a public
  repository purely for transparency and ease of install);
- free for non-production use (evaluation, development, staging) and for a
  30-day production trial that starts automatically on install;
- gated for production use beyond the trial behind a per-instance commercial
  license purchased from Oduist;
- eventually open source, so customers are protected against abandonment.

We considered a **custom, BSL-derived** license that additionally forbade
redistribution (copying to other public repos, reselling to a partner's
clients). It matched the commercial intent but could not use the "Business
Source License" name (MariaDB's trademark covenants forbid modifying the Terms),
and — more importantly — it was unnecessary: under BSL every copy stays under
BSL and production use is gated everywhere, so a redistributor cannot give
anyone a working production product for free. The redistribution ban bought
little and cost the recognisable name and the clean trademark posture.

A recurring worry was "what if a customer just deletes the licensing code?" BSL
restricts **use**, not **modification** — it explicitly permits modification.
Removing the check is allowed, but it grants no production rights: running the
Licensed Work in production past the trial without a commercial license is a
breach and copyright infringement regardless of whether the check is present.
The in-product check is therefore a UX reminder and tripwire; the enforceable
wall is the production-use restriction, which needs no anti-circumvention
clause (and adding one would forfeit the BSL trademark).

## Decision

Adopt the **canonical Business Source License 1.1** (MariaDB template, unmodified
Terms) for all Connect modules, with these Parameters:

- **Licensor:** Oduist OÜ (https://oduist.com).
- **Licensed Work:** the module in whose directory the `LICENSE` file sits,
  named per module (e.g. "Oduist Connect FreeSWITCH"). Copyright
  `© 2024-2026 Oduist OÜ`.
- **Additional Use Grant:** production use permitted for 30 days after first
  install on an instance, for evaluation.
- **Change Date:** `2030-07-15` for the versions published today. The date is
  **per module, per version** — it is bumped forward on each new major release,
  so newer code stays proprietary longer while older releases convert on
  schedule. Already-published versions keep their original Change Date (it is
  not extended retroactively).
- **Change License:** GNU LGPL-3.0-or-later (GPL-compatible, satisfying BSL
  covenant 1).
- **Purchase path:** stated in the customizable notice line — buy in-app via the
  built-in license manager; pricing at https://oduist.com/pricing.

Ship a `LICENSE` file in **each** of the 14 module directories. All files are
byte-identical except the `Licensed Work` module-name line. Keep
`'license': 'Other proprietary'` in every manifest (Odoo has no BSL enum value;
"Other proprietary" is the correct manifest classification for source-available
non-OSI terms).

Per-instance binding, perpetual/irrevocable status of a paid license, price and
payment mechanics are **commercial-agreement terms**, not license text; the BSL
"purchase a commercial license from the Licensor" clause and the notice line
point to them. They live in the EULA/offer, the in-app license manager and
`oduist.com/pricing`.

## Consequences

- One recognised, source-available license across all 14 modules; the six
  modules that lacked a LICENSE now have one.
- Redistribution of source is permitted by BSL, but every copy remains under
  BSL and production use stays gated per instance, so the commercial model holds
  without a redistribution ban.
- On the Change Date each version becomes LGPL-3.0-or-later; the trial,
  per-instance licensing and all BSL restrictions fall away for that version.
- Bumping the Change Date is a release-time action on new major versions, not a
  per-commit chore. It is edited only in the `LICENSE` `Change Date:` line.
- No code change to the `oduist.license` enforcement is required; the license
  text now matches its behaviour (trial, per-instance purchase, graceful stop
  that disables only the module's own features).
- This is an engineering-grade adaptation of the MariaDB template; the final
  text and the Estonian/commercial specifics should be reviewed by counsel
  before public release.

## References

- Business Source License 1.1 — https://mariadb.com/bsl11/
- `connect/models/license.py` — `oduist.license` enforcement model.
- `docs/admin/licensing.md` — admin-facing trial and purchase documentation.
