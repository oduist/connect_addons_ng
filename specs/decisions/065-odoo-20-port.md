# 065 — Odoo 20 port: unified ir.access, typed config parameters, schedule-owned timezone

## Problem

Odoo 20 (series `20.0`) breaks four APIs the suite relies on:

1. `ir.model.access` and `ir.rule` were merged into a single `ir.access`
   model (`operation` = subset of `crud`, optional `domain`; a group access
   is a *permission* unioned with the user's other accesses, a group-less
   access is a *restriction* intersected with them).
2. `ir.config_parameter.get_param()/set_param()` were replaced by typed
   accessors (`get_str`, `set_str`, …).
3. `Registry.clear_cache()` was removed; the replacement is
   `env.transaction.invalidate_ormcache()`.
4. `resource.calendar` lost its `tz` field (calendars became
   timezone-agnostic; timezone now lives on the resource/company).

## Decision

**Security.** Every `security/*.xml` on the `20.0` branch declares
`ir.access` records (same XML ids as the old ACLs). Conversion rules:

- old ACL → `ir.access` with `operation` letters from the `perm_*` flags;
- an `ir.rule` whose domain is `[(1,'=',1)]` is dropped — under union
  semantics the group's plain access already grants everything, so the
  "admin/webhook sees all" opener rules are redundant;
- an `ir.rule` with a real domain (user sees own records) is folded into
  the same group's access record as its `domain` field. This is only
  equivalent when the ACL's operations are a subset of the rule's — the
  converter asserted that, and it holds everywhere in the suite.

`connect/security/record_rules.xml` is kept as an empty shell so manifests
stay aligned across series. `connect_memory` ships `ir.access.csv` (the CSV
filename selects the model, so this one manifest data entry differs from
older series).

**Python stays byte-identical across series** (the standing invariant): the
three Python-level breaks are handled by `release.version_info[0] >= 20`
branches that are dead code on ≤ 19. Because `get_param`/`set_param` had
~20 call sites, they go through two thin compat helpers —
`get_system_param(env, key, default)` / `set_system_param(env, key, value)`
in `connect/models/license.py` (re-exported via `connect.models.settings`,
which provider modules already import from) — instead of per-site branches.
`registry.clear_cache()` sites got an inline `>= 20` arm, matching the
existing `>= 17` branching idiom at those sites.

**Schedule timezone.** On ≥ 20, `connect.schedule.tz` is an owned, required
Selection (default: user tz) instead of a related field onto the calendar;
`_get_tz()` and `connect_freeswitch_website` read `schedule.tz`, which
behaves identically on every series. Admins now pick the timezone on the
schedule form on Odoo 20 — there is nowhere else to inherit it from.

## Rejected

- Emitting converted rules as separate `ir.access` records next to the
  ACLs: under 20's union semantics the domain-less ACL access would win,
  silently widening user access — the rules must be *folded*, not copied.
- Forking the affected `.py` files per series: forbidden by the
  cross-branch invariant; the compat helpers keep the diff to XML/security
  assets plus the manifest version prefix.

## Consequences

The compat-helper arms and the `>= 20` branches must be backported verbatim
to `19.0` (and older series) to restore the byte-identical invariant — they
are no-ops there. `connect_vonage` (pre-ADR-031, uninstallable) and the two
Enterprise-helpdesk modules were not exercised by the 20.0 install test.
