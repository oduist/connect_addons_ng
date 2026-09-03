# ADR-048: FS Queue fallback in callflows — route by the `fs_fifo_<id>` handle

**Status:** Accepted
**Date:** 2026-06-24
**Issue:** GitHub [#117](https://github.com/oduist/connect_addons_ng/issues/117), Linear ODU-43
**Relates to:** [ADR-013](013-freeswitch-fifo-queues.md) (FIFO queues via mod_fifo)

## Context

Issue #117 reports that the **"Fallback Queue"** on a callflow does nothing: when a
ring group times out or nobody answers, the caller is **dropped** instead of being
routed into the FS Queue. The issue diagnoses this as *"no queue model exists
anywhere"* and asks to build a new `connect.freeswitch.queue` model on
`mod_callcenter`.

That diagnosis is **wrong**. Investigation (reproduced on a clean Odoo 19
environment, `19.0-fs-queue`) establishes:

- The FS Queue feature **already exists** (ADR-013): model `connect.fs_fifo`,
  dialplan template `dialplan_fs_fifo`, static consumers served via
  `fifo.conf.xml`, and the `connect.callflow.fs_fifo_id` ("FS Queue") field.
  `mod_fifo` landed 2026-04-22 (PR #30); #117 was filed **2026-06-11**, i.e.
  against code that already has the queue.
- The ring-group fallback **is** wired: `dialplan_ring_group` emits
  `<action application="transfer" data="{{ fifo_number }} XML default"/>` after a
  failed bridge — **but only inside `{% if fifo_number %}`**.

### Root cause (reproduced)

`fifo_number` is the queue's `exten_number`: a stored related field on
`connect.fs_fifo.exten` (the queue's `connect.exten`). A queue has **no extension**
until an admin manually fills in the extension form — the "Extension" stat button's
`create_extension()` (`connect/models/exten.py:117`) only returns an
`ir.actions.act_window` that opens that form; **it creates nothing by itself**.

When a queue without an extension is chosen as a callflow fallback:

- `_generate_ring_group_dialplan` / `_generate_ivr_dialplan` compute
  `fifo_number = ''`, so the `{% if fifo_number %}` transfer block is **silently
  omitted** → the caller is dropped after the ring timeout.
- The standalone `_generate_fifo_fallback_dialplan` uses
  `exten_number or str(id)`, but that `str(id)` fallback is **illusory**: the
  FreeSWITCH XML dialplan controller resolves transfer targets only by
  `connect.exten.number` (`freeswitch_xml.py:413` exact, `:422` regex). With no
  `connect.exten`, `transfer <id>` matches nothing. There is **no** "fifo by bare
  id" route.

**Conclusion:** a queue is reachable from the dialplan **only if it has a
provisioned `connect.exten`**. Reproduction: a ring-group callflow whose fallback
queue has no extension generates an extension with **no `bridge` and no
`transfer`** — only variable-setting actions, then an implicit hangup. Exactly the
symptom in #117.

So #117 is a **bug in the existing mod_fifo feature**, not a missing feature.
Rebuilding on `mod_callcenter` would duplicate working code and reverse ADR-013's
deliberate choice.

## Options

1. **Build `connect.freeswitch.queue` on `mod_callcenter`** (the issue's literal
   "Expected Fix"). Rejected: duplicates the mod_fifo feature, large effort,
   reverses ADR-013; no product need for ACD agent-state/tiers right now.
2. **Emit the transfer unconditionally with an `or str(id)` fallback** in the
   ring-group/IVR templates, mirroring the standalone path. Rejected on its own:
   routing is by `exten.number` only, so `str(id)` transfers to a dead target.
3. **Auto-provision an extension for the queue on create** so every queue is
   routable. Fixes the root cause at the source.
4. **Validate** — raise a clear error when a queue without an extension is used as
   a destination. Removes the silent failure but keeps the manual extension step.

5. **Route the queue by an internal handle `fs_fifo_<id>`** — make the queue reachable
   from the dialplan without any user-facing extension; the callflow always transfers to
   that handle. **Chosen.**

## Decision

Adopt **(5): route the queue by the internal handle `fs_fifo_<id>`.**

> Auto-provisioning (3+4) was initially chosen but then rejected by the deployment owner:
> it pollutes the numeric extension namespace and is "magic". Option 5 needs no extension,
> no auto-numbering, and no migration, and it also repairs the standalone path.

- New helper `connect.fs_fifo._dialplan_target()` → `self.exten_number or 'fs_fifo_%d' % self.id`.
  A user-facing extension stays **optional** (only for direct dialing) and takes precedence.
- `connect.fs_fifo.generate_dialplan` self-names by the handle when it has no exten:
  `number = exten.number if exten else self._dialplan_target()`, so the rendered condition
  `^fs_fifo_<id>$` matches the transferred destination.
- The dialplan controller `_route_internal` gains a branch: a destination matching
  `^fs_fifo_(\d+)$` resolves the queue and returns `fifo.generate_dialplan(params)` —
  mirroring the existing synthetic-destination branches (`cf_call_*`, `cf_invalid_*`).
- The three callflow paths (`_generate_ring_group_dialplan`, `_generate_ivr_dialplan`,
  `_generate_fifo_fallback_dialplan`) compute `fifo_number = fs_fifo_id._dialplan_target()`
  — always non-empty when a fallback queue is set, so the `{% if fifo_number %}` transfer
  block is always emitted. This also fixes the previously **dead `str(id)`** in the standalone
  path (which never routed, because the controller only matched by `connect.exten.number`).

No silent omission, no auto-numbering, no manual-extension requirement, **no migration**.
`mod_fifo` and ADR-013 stand; no FreeSWITCH image rebuild (nothing under `deploy/` changes).

## Consequences

- A queue is routable as a callflow/IVR fallback the moment it exists — no extension needed.
- Assigning a user-facing extension to a queue remains supported (direct dialing) and wins
  in `_dialplan_target()`.
- **Tests (TDD):** (a) a ring-group callflow with an extension-less fallback queue renders a
  `transfer … fs_fifo_<id>`; (b) the controller routes `fs_fifo_<id>` to the queue dialplan.
- **Docs/specs:** document the `fs_fifo_<id>` internal handle and that a queue extension is
  optional.
- Issue #117 reclassified from "feature request (mod_callcenter)" to "bug fix in mod_fifo
  fallback routing".
- Separate runtime bug found while verifying live (ODU-44): mod_fifo isn't re-read after a
  queue's members change, so agents aren't rung until `reload mod_fifo`. Tracked separately.
