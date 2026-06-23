# ADR-030: N-leg bridge call convergence

**Status:** Accepted
**Date:** 2026-06-23
**Builds on:** ADR-022 (orphan-field backfill) and the original
`reconcile_bridge_link` race fix (commits b0c7094, 65e3e23, e95bf55)
**Issue:** ODU-42

## Context

A single FreeSWITCH call kept producing **two** `connect.call` rows.
Confirmed on `19.0-twilio-fs-compat` for an internal call 101→100:

| ch | sid | parent_sid | parent_channel | call | status | dur |
|----|-----|-----------|----------------|------|--------|-----|
| 1 | 405a (b-leg, lost race) | 371a | 3 | **3** | failed | 0 |
| 2 | 8b447 (b-leg, answered) | 371a | 3 | 2 | completed | 4 |
| 3 | 371a (a-leg) | 8b447 | 2 | 2 | completed | 4 |

`ch1.parent_channel.call = 2` but `ch1.call = 3`: the leg is **linked
yet on its own duplicate call**, and `reconcile_bridge_link` was a
permanent no-op for it (no longer an orphan).

Two facts the prior fixes did not account for:

1. **A bridged call is N legs, not two.** The dialplan bridges to
   `user/100`, whose dial-string (`_directory_for_user_bridge`,
   `connect_freeswitch/controllers/freeswitch_xml.py:178-196`) is a
   **parallel fork** to every callee contact (SIP endpoints + webrtc),
   comma-joined. The winner answers; the losers tear down (0s/`failed`).
   `mod_xml_cdr` runs with `log-b-leg=true` + `prefix-a-leg=true`
   (`deploy/freeswitch/conf/autoload_configs/xml_cdr.conf.xml`), so
   **every leg posts its own CDR** → one `connect.channel` per leg. So
   N = 1 a-leg + M b-legs (2, 3, 4…), all sharing the a-leg as their
   `signal_bond` parent (stored in `parent_sid`).

2. **The merge was gated on link-absence.** `reconcile_bridge_link`
   merged calls only as a side effect of *establishing* the parent link
   (forward branch `if not ch.parent_channel`; reverse branch filtered
   orphans by `parent_channel = False`), and `_merge_calls` early-returned
   on `not parent.call`. Under concurrent CDR delivery a losing b-leg got
   `parent_channel` set while the a-leg's `call` was not yet visible →
   link set, calls **not** merged. Afterwards the channel is no longer an
   orphan, so no later pass ever revisits it → permanent duplicate.

ADR-022 / the original race fix handled the **2-leg** race where the
*missing link* was the symptom. They did not anticipate >2 legs nor the
"link present, call unmerged" state.

## Decision

Replace the link-gated, pairwise, 2-leg merge with a single **idempotent
component-convergence** pass in core, and remove the duplicated inline
merge in `connect_freeswitch`.

### 1. `connect.models.channel.Channel.reconcile_bridge_link` — converge

Walk the **bridge component** (the transitive closure of the symmetric
`parent_sid` <-> `sid` / signal_bond relation), set `parent_channel`
wherever the parent is present in the component, then collapse every
distinct `call` in the component into one canonical call:

- `_bridge_component(channel)` — bounded BFS over
  `['|', ('parent_sid','in',sids), ('sid','in',parent_sids)]`.
- `_converge_calls(channels)` — canonical = oldest call (min id); for each
  channel on another call, reassign to canonical, `_backfill_call` the
  emptied call's fields (ADR-022), then `unlink()` it once empty.
- `_backfill_call(survivor, orphan)` — extracted from the old
  `_merge_calls`; copies caller/called/partner where the survivor's slot
  is empty.

Convergence is driven by **call inequality inside the component**, not by
whether `parent_channel` was just established — so a linked-but-unmerged
leg is collapsed. Idempotent (≤1 call → no-op). Order-independent: the
last reconcile sees the full committed component; an out-of-order late leg
converges on its own pass.

`_merge_calls` is removed (its only caller was the old reconcile).

### 2. `connect_freeswitch.models.call.Call.on_freeswitch_cdr` — de-dup

Remove the in-transaction reverse-orphan link+merge block. It ran under
the racy REPEATABLE-READ snapshot (so it could not see sibling legs
anyway) and carried the same link-gated flaw. The post-commit
`reconcile_bridge_link` (called from `freeswitch_cdr.py`) now covers it.
The orphan-recording linking block is kept.

## Options considered

**Option A (chosen): component convergence + consolidation.** One robust,
idempotent, order-independent code path; handles arbitrary leg counts;
self-heals already-stuck rows. Slightly more code in core, but removes the
duplicated merge in the provider.

**Option B: patch the existing gates** (also merge when
`parent_channel.call != call`; drop the `not parent.call` early-return).
Smaller diff, but keeps three overlapping merge sites and stays
2-leg-shaped — fragile for >2 legs and easy to regress. Rejected.

**Option C: advisory lock to serialize CDR processing.** Already rejected
twice (commit 65e3e23): `pg_advisory_xact_lock` is itself a SELECT and
fixes the transaction snapshot at acquisition, so it does not prevent the
race. The post-commit fresh snapshot is the correct mechanism.

**Option D: FreeSWITCH-side — stop forking / disable `log-b-leg`.** Would
reduce leg count, but parallel fork to multiple contacts is a wanted
feature (ring all devices), and per-leg CDRs are useful. Treating N legs
as normal in Odoo is the right layer. Rejected.

## Consequences

- Any bridged call (any leg count, any CDR order) collapses to exactly one
  `connect.call`; existing stuck duplicates self-heal on the next
  `reconcile_bridge_link` for any of their sids.
- `parent_channel` links stay correct, so the connect_twilio recording
  lookup (`connect_twilio/models/recording.py:69`) and the channel views
  are unaffected.
- One merge implementation instead of three overlapping ones.
- No migration: the one pre-existing duplicate on `19.0-twilio-fs-compat`
  is healed by a one-off `reconcile_bridge_link` call (per ODU-42 scope).
- 18.0 port is a follow-up (same core helpers, cross-branch version
  alignment).
