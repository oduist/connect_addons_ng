# Port `connect_memory` + `connect_memory_sale` into `connect_addons_ng`

**Date:** 2026-07-17
**Branch:** `nicolaepostica/port-connect-memory` (target `origin/19.0`)
**Type:** Module port (faithful copy + adaptation to repo conventions)

## Goal

Port two working Odoo modules from the legacy `connect_addons` repo
(`/Users/poligon/Workspace/odoo19/connect_addons/`) into this repository as
first-class, "native" modules that follow all `connect_addons_ng` conventions
(manifest versioning, cross-series Python invariant, security groups, `specs/`,
`docs/`, `AGENTS.md`, ADR).

Business logic is **not** changed — the architecture is fixed by the source.
This is a port, not a redesign.

## What the modules do

### `connect_memory` (base)

External AI memory for Odoo, engine-neutral (Hindsight, Cognee, …). Odoo is an
**event emitter**: it never calls the memory engine. It writes neutral domain
events into `connect.memory.outbox`; an external per-engine service pulls them
over HTTP, loads them into the brain, and writes answers back into
`connect.memory.inbox`.

- **`connect.memory.outbox`** — outgoing domain events (JSON `payload`,
  idempotent `enqueue` on `dedup_key`+`content_hash`, `fetch_batch`/`ack` for
  the HTTP pull, `_cron_vacuum_sent` retention that drops bulky payloads but
  keeps a dedup tombstone).
- **`connect.memory.inbox`** — reflect/recall requests + engine answers
  (`submit`, `claim_batch`, `store_answer`).
- **`connect.memory.mixin`** (abstract) — scope/body helpers, master switch
  `_memory_enabled`, and the per-module Connect-license gate `_memory_emit`
  (cached by day+module so backfill of hundreds of thousands of messages does
  not RS256-verify per event).
- **`mail.thread` override** — `message_post` captures real external
  correspondence (email/comment with an external author or recipient) on the
  chatter of any document. Never breaks the business operation (wrapped in
  try/except).
- **`connect.memory.backfill` + `.wizard`** — cron-driven historical replay of
  all partners' correspondence; resumable via a message-id cursor, idempotent.
- **`res.partner`** — `memory_event_count` smart button, `action_memory_events`,
  `action_memory_backfill` (per-partner), `action_memory_summary` (queues a
  `reflect` request).
- **`connect.settings` (`_inherit`)** — `memory_enabled`,
  `memory_service_url`/`_token`, `memory_default_engine`,
  `memory_outbox_retention_days` + a standalone "Memory" settings form and menu.
- **Controller** — four JSON-RPC routes
  `/connect_memory/{outbox,inbox}/{fetch,ack|answer}`, token-protected
  (`memory_service_token`, via `token` param or `X-Memory-Token` header).
- **Data** — 2 crons (vacuum, backfill), registration in `ODUIST_MODULES`,
  `post_init_hook` (starts trial clock + license refresh).
- **`deploy/`** — external sidecar `hindsight_gateway.py` (Dockerfile,
  docker-compose, requirements) that drives the Hindsight engine.

### `connect_memory_sale` (domain)

Memory events for sales/finance. Depends on `connect_memory`, `sale`,
`account`. Registers itself in `ODUIST_MODULES`.

- **`connect.memory.sale.mixin`** (abstract) — envelope builders shared by all
  sale paths.
- **`sale.order`** — `created`, `lifecycle` (confirmed/cancelled/locked),
  `state_change` (renegotiation diff of tracked scalars + order lines).
- **`account.move`** — `posted` invoice/refund events (customer + vendor).
- **`account.partial.reconcile`** — payment events with `late_payment` signal.
- **`res.partner._memory_sale_payment_digest`** — hourly cron emitting a
  payment-behavior `observation` per commercial partner (avg/max days late,
  late ratio), with a per-partner staleness cursor
  (`memory_payment_digest_date`).
- **Data** — payment-digest cron + 3 `ir.config_parameter` tuning knobs.

## Compatibility (verified)

The `connect` module in this repo already provides everything the modules rely
on: `oduist.license` (`check_license`, `update_license_status`),
`ODUIST_MODULES`, `connect.settings.get_param`/`set_param`. The source is
already written cross-series (`release.version_info[0] >= 19` branches for the
`models.Constraint` vs `_sql_constraints` and for the `jsonrpc` vs `json` route
type), so the **byte-identical-Python-across-series invariant holds out of the
box** — no `.py` changes are needed for version compatibility.

## Adaptation to `connect_addons_ng` conventions

1. **Manifest versions:** `1.0.1 → 19.0.1.0.1` (`connect_memory`),
   `1.0.0 → 19.0.1.0.0` (`connect_memory_sale`).
2. **Migrations:** rename `connect_memory/migrations/1.0.1/` →
   `migrations/19.0.1.0.1/` (same `post-migrate.py`). On fresh ng installs this
   never fires (it is the legacy `ir.config_parameter → connect.settings` move);
   kept for series parity.
3. **Security → repo groups (decision A):** replace `base.group_user` /
   `base.group_system` with the repo's Connect groups:
   - `connect.memory.outbox` — `connect.group_user` read; `connect.group_admin`
     full CRUD.
   - `connect.memory.inbox` — `connect.group_user` read+create;
     `connect.group_admin` full CRUD.
   - `connect.memory.backfill` / `.backfill.wizard` — **admin only**
     (`connect.group_admin` full CRUD; no user access — infrastructure models).
   - Gate the `res.partner` memory buttons/smart-button visibility on
     `connect.group_user` so a non-Connect internal user does not hit an access
     error opening the events list. (`memory_event_count` compute already uses
     `sudo()`, so the field is safe.)
4. **`deploy/`:** copy the sidecar, but **do not commit the real
   `deploy/.env`** — only `.env.example` and `deploy/.gitignore` (which already
   ignores `.env`). No Docker image is built or pushed in this task.
5. **Icon + Apps Store description (decision B):** generate
   `connect_memory/static/description/{icon.png,index.html}` (and the same for
   `connect_memory_sale`) via the `writing-odoo-module-description` skill; add
   `'images': ['static/description/icon.png']` to both manifests.
6. **`AGENTS.md`:** add both modules to the Modules list, the dependency note,
   the `specs/` list, the `tests/` tree, and the `run_odoo_tests` list.
7. **`specs/`:** create `specs/connect_memory.md` and
   `specs/connect_memory_sale.md` in the house spec format.
8. **`docs/`:** add `admin/memory-setup.md` and `user/memory.md`, wired into
   `mkdocs.yml` nav.
9. **ADR:** add `specs/decisions/043-connect-memory-outbox-inbox.md` recording
   the "external AI memory via outbox/inbox contract; Odoo never calls the
   engine" decision.
10. **Tests:** port all existing `tests/` from both modules unchanged (they are
    already version-neutral) and register them in each `tests/__init__.py`.

## Non-goals

- No change to the memory event schema, capture rules, or sidecar logic.
- No Docker image build/push for the Hindsight gateway.
- No new provider engines.

## Verification

Via oduflow in the branch environment:

1. Commit + push the branch, `pull_and_apply`.
2. Install `connect_memory`, then `connect_memory_sale`.
3. `run_odoo_tests connect_memory` and `run_odoo_tests connect_memory_sale`.
4. UI smoke test (agent-browser): open the Connect → Memory settings form, flip
   `memory_enabled`, confirm the `res.partner` memory smart button + actions
   render for a Connect user.

## Open decisions — resolved

- **A (security):** adapt to `connect.group_user`/`connect.group_admin`
  (native repo convention), backfill/wizard admin-only.
- **B (icon/description):** generate both via the description skill in this
  task.
