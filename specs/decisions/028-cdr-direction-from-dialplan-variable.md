# ADR-028: Resolve CDR call direction from the dialplan `odoo_call_direction` variable

## Status
Accepted

## Context

The FreeSWITCH CDR handler (`connect_freeswitch.controllers.freeswitch_cdr`)
derives a call's direction from FreeSWITCH's **native per-leg direction**, read
from `<channel_data><direction>` and mapped through:

1. `_process_cdr_locked` (`connect_freeswitch/models/call.py`):
   FS `outbound` → `technical_direction='outbound-api'`, else `'inbound'`.
2. `_determine_direction` (core `connect/models/call.py`):
   `outbound-api` → `outgoing`; `inbound` **with** `caller_pbx_user` →
   `outgoing`; `inbound` **without** `caller_pbx_user` → `incoming`.

FreeSWITCH's native direction is a *transport* property: the UA / originate leg
of an **outbound** call is `inbound` from FS's own perspective (the UA sends its
INVITE *into* FS). When a call is launched via `fs_cli -x "originate ..."` (or any
path that doesn't seed `caller_pbx_user`), that leg lands at
`technical_direction='inbound'` with no `caller_pbx_user`, so
`_determine_direction` returns `incoming` for a call that actually left the system
outbound. Reproduced during REISO outbound testing (issue #43).

The dialplan already records the **business-logic** direction on the channel — it
sets `odoo_call_direction=inbound` on inbound DID routes and
`odoo_call_direction=outgoing` on outgoing routes (`data/fs_templates.xml`) — but
the CDR processor never read that variable.

## Decision

Honour `odoo_call_direction` in the CDR handler; fall back to the native FS
direction only when it is absent.

1. **Parse it.** `_parse_cdr_xml` extracts `odoo_call_direction` from the CDR
   `<variables>` (a plain word, so no URL-decoding) and returns it on the
   `cdr_data` dict (`None` when absent).

2. **Prefer it.** A new pure helper
   `connect.call._cdr_technical_direction(cdr_data)` resolves
   `technical_direction`: `odoo_call_direction='outgoing'` → `outbound-api`,
   `='inbound'` → `inbound`, otherwise the previous native-direction mapping
   (`direction='outbound'` → `outbound-api`, else `inbound`).
   `_process_cdr_locked` calls the helper instead of inlining the mapping.

This keeps the fix entirely inside `connect_freeswitch`: core's
`_determine_direction` and the provider-agnostic boundary are untouched. The
B-leg of an outbound call and both legs of an inbound DID call do not carry
`odoo_call_direction` (the dialplan `set` is not `export`ed), so they fall through
to the unchanged native mapping — no regression. Call direction is decided by the
first (parent-less) leg in `process_call_event`, which for an outbound call is the
UA / originate leg this fix corrects.

## Alternatives considered

- **Change core `_determine_direction` to accept an explicit direction.**
  Rejected: it pushes FreeSWITCH-specific knowledge into the technology-agnostic
  core and widens the core/provider boundary for a provider-local concern.

- **Seed `caller_pbx_user` on every originate.** Rejected: it only helps Odoo's
  own click-to-call path and does nothing for raw `fs_cli` originates or any
  third-party origination — the exact scenario in the report. The dialplan
  variable is authoritative regardless of who launched the call.

- **Infer direction from the channel name / gateway leg.** Rejected as brittle:
  it re-derives, by string heuristics, the very fact the dialplan already states
  explicitly.

## Cross-branch backport

Per `CLAUDE.md` versioning rules, the same fix ports to the `18.0` branch with the
aligned tail version: `connect_freeswitch` moves `19.0.1.10.3 → 19.0.1.10.4` and
`18.0.1.10.3 → 18.0.1.10.4`. Code-only change — no schema change and no migration
script. The backport ships as a separate PR.
