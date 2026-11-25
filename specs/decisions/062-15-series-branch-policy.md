# 062 — 15.0 series branch: verbatim mirror, with connect and connect_telnyx really ported

## Problem

The product ships on the 17.0/18.0/19.0 Odoo series under the byte-identical
Python invariant (see AGENTS.md, Version Compatibility). A customer deployment
also runs Odoo 15. The `15.0` branch so far has been a verbatim fast-forward
mirror of `19.0` (same commit hashes plus squashed backport commits, `19.0.x`
manifest versions, `19.0.*` migration folders, 19-style view XML) — none of it
installable on an actual Odoo 15 server: the views use `<list>`,
expression-valued `invisible=`, `<chatter/>`; the security data uses
`res.groups.privilege` and `user_ids`; the crons lack `numbercall`; the whole
frontend is OWL 2.

## Options considered

1. **Really port every module to Odoo 15.** Rejected: most provider modules
   are not used on the 15 deployment, and several depend on web-client APIs
   that have no Odoo 15 counterpart at all.
2. **Keep the pure mirror.** Rejected: the modules that ARE used on 15
   (`connect`, `connect_telnyx`) do not install.
3. **Mirror everything, really port only `connect` and `connect_telnyx`.**
   Chosen.

## Decision

The `15.0` branch remains a verbatim content mirror of `19.0` (keeping
`19.0.x` manifest versions and `19.0.*` migration folders for the mirrored
modules), **except** `connect` and `connect_telnyx`, which are really ported:

- **Python stays byte-identical** to `19.0` — the invariant extends to 15.0.
  Where Odoo 15 behaves differently, the shared `.py` files branch on
  `release.version_info[0]` (bus `_sendone`, `env._` via
  `connect/models/compat.py:env_translate`, act_window `view_mode`,
  `Constraint` vs `_sql_constraints`, …).
- **XML is downgraded to Odoo 15 syntax** on the 15.0 branch only:
  `<tree>` instead of `<list>`, `attrs="{...}"` domains instead of
  expression attributes, `column_invisible` → `invisible`, `<chatter/>` →
  the `oe_chatter` div, `res.groups` `category_id`/`users` instead of the
  19-only `privilege_id`/`user_ids`, and `numbercall="-1"` on every cron.
- **The JS frontend is a maintained OWL 1 fork** on the 15.0 branch: same
  file layout, components rewritten for OWL 1.x and the Odoo 15 web client
  (global `owl`, lifecycle methods, `t-esc`, `on/off/trigger` EventBus,
  legacy `patch`, longpolling bus, legacy field widgets for
  `phone`/`telnyx_voice`). Pieces with no Odoo 15 counterpart are excluded
  from the 15 assets rather than shipped broken. The vendored
  `@telnyx/webrtc` bundle and the Telnyx session logic are version-neutral
  and shared.
- **Manifests and migrations are series-correct for the two ported modules**:
  `15.0.<product tail>` versions and `migrations/15.0.*` entry points
  (calling the same Python helpers). All other modules keep the mirror's
  `19.0.x` numbering.

## Consequences

- A backport to 15.0 is: mirror-sync the tree to the 19.0 tip, then re-apply
  the 15-only XML/JS/manifest deltas for `connect` and `connect_telnyx`.
  Any `.py` drift between 15.0 and 19.0 is a bug.
- The OWL 1 frontend fork is real dual maintenance, accepted for two modules
  only. JS changes on 19.0 must be mirrored manually into the 15.0 variants.
- The mirrored (unported) modules on 15.0 are not installable on Odoo 15 and
  are not supported there; they exist only to keep the branch a faithful
  content mirror.
