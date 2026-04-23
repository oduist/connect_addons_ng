# 014 — Durable CDR inbox replaces inline advisory-lock handler

Supersedes: [013 — Serialize FreeSWITCH sibling-leg CDR processing](./013-freeswitch-cdr-sibling-lock.md)

## Problem

ADR 013 solved the A-leg / B-leg CDR merge race with a session-scoped
`pg_advisory_lock` plus three manual `cr.commit()` calls inside
`connect.call.on_freeswitch_cdr`. It worked, but:

- **Breaks Odoo's HTTP transaction model.** The HTTP handler is supposed to
  own exactly one commit; injecting commits inside a model method means
  Odoo's built-in retry on serialization failure can no longer wrap the
  handler, and a post-commit exception leaves partially-written state that
  Odoo will not roll back.
- **Stuck locks on worker crash.** Session-scoped advisory locks are only
  released when the PG session ends. If the Odoo worker is killed between
  `pg_advisory_lock` and `pg_advisory_unlock`, the lock lingers until the
  connection is reaped, blocking every sibling CDR with the same `chain_id`
  in the meantime.
- **Exception fragility.** The chain-lock `try/finally` assumes the
  controller owns the outer transaction. Mixing that with Odoo's own
  commit at request end produced a non-obvious contract that future
  contributors would have to reason about to touch this file safely.

The architecture analysis in `ANALYSIS.md` flagged this as a P0 issue
(§3.1 «Транзакционный кошмар в `on_freeswitch_cdr`»).

## Options considered

1. **Keep advisory lock, harden error handling.** Smaller diff but does not
   address the model-layer commits or the stuck-lock failure mode.
2. **Introduce `queue_job` (OCA).** Battle-tested, but adds a heavy
   external dependency that this commercial addon does not otherwise use,
   and ships its own admin UI / configuration surface.
3. **Durable CDR inbox table + `ir.cron`.** The webhook persists the raw
   payload and returns 200 immediately. A cron worker claims pending rows
   via `FOR UPDATE SKIP LOCKED`, processes all rows of a chain in one
   transaction, commits once, releases the row locks. No advisory lock,
   no manual commits inside the model method.

## Decision

Option 3.

### Architecture

- New model `connect.freeswitch.cdr.inbox` stores the raw XML payload,
  lightly-extracted `uuid` / `chain_id`, processing state, attempt
  counter, and last error.
- `FreeSwitchCDRController.cdr_webhook` now only calls
  `inbox.receive(payload)` and returns 200. All parsing is deferred.
- `inbox.process_pending()` is the cron entry point:
  1. `SELECT … FOR UPDATE SKIP LOCKED LIMIT 1` picks one pending
     `chain_id` (workers cannot collide on the same chain — other chains
     are processed in parallel by other workers).
  2. A second `SELECT … FOR UPDATE` locks every pending row of that
     chain in insertion order.
  3. Each row is processed inside a savepoint, so a single bad payload
     does not poison its siblings.
  4. On success: state `done`. On failure: `attempts++`, state
     `pending` until `MAX_ATTEMPTS`, then `failed`.
  5. One commit at the end releases the chain's row locks.
- `inbox.reap_stuck()` (every 5 min) resets rows stuck in `processing`
  (crashed worker) back to `pending`.
- `inbox.vacuum(days=7)` deletes old `done` rows.
- `connect.call.on_freeswitch_cdr` no longer handles locking or commits;
  its body is now a thin wrapper over the previously-inner
  `_process_cdr` (was `_process_cdr_locked`).

### Why this does not reintroduce the REPEATABLE-READ snapshot problem

ADR 013's session-lock + manual-commit dance existed because Odoo runs
under REPEATABLE READ: the transaction's snapshot freezes at the first
statement. A worker that held the lock had to commit its writes
*before* releasing, and the waiting worker had to start a fresh
transaction *after* acquiring, for the merge query to see the sibling's
committed channel.

In the inbox model the sibling rows are processed inside the *same*
transaction of the *same* cron invocation, in deterministic FIFO order.
The second row's query naturally sees everything the first row wrote
because both share a snapshot opened at the beginning of
`_process_one_chain`. The advisory lock becomes unnecessary — the row
lock on the inbox is the only serialization primitive, and it composes
cleanly with PostgreSQL's row-locking semantics.

### Cost

- ~100 ms → up to ~60 s of added CDR-to-UI latency (cron runs every
  minute; Odoo does not expose sub-minute `ir.cron` intervals). For
  CRM-style call logging this is well within the acceptable envelope.
  If a customer needs sub-second latency in the future, the inbox
  already exposes a `process_pending()` method that can be invoked from
  the webhook as a best-effort fast path, with the cron remaining as
  the correctness backstop.

### Fast-path singleton (webhook inline call)

`FreeSwitchCDRController.cdr_webhook` invokes `Inbox.process_pending()`
inline after `receive()` so the call materialises in <100 ms instead of
waiting for the next cron tick. When FreeSWITCH bursts sibling CDRs
(A-leg and B-leg end within milliseconds of each other) every webhook
hit would otherwise start its own `process_pending` loop in parallel —
wasted work, even though `FOR UPDATE SKIP LOCKED` keeps it correct.

Guarded with a session-scoped `pg_try_advisory_lock(_INLINE_LOCK_KEY)`:

- First webhook acquires the lock and runs `process_pending`.
- Concurrent webhooks see the lock taken, skip the inline call, and
  return 200. Their row is already in the inbox, so the running
  worker's `BATCH_CHAINS` loop (or the cron backstop) will pick it up.
- Lock is session-scoped, not transaction-scoped, because
  `_process_one_chain` commits mid-flight and the singleton guarantee
  must span those commits. Released in a `finally` on the same cursor.

This is distinct from ADR 013's per-chain `pg_advisory_lock`: that was
a model-layer lock held across a sequence of commits to serialise
sibling merges. This one is a controller-layer dedup for the inline
fast-path only; chain-level serialisation still lives in the inbox's
row-lock flow.
- One extra table and three cron entries. Admin UI surfaced under
  **Connect → Configuration → CDR Inbox**, scoped to
  `connect.group_admin`.

## Consequences

- **P0 finding §3.1 from `ANALYSIS.md` is closed.** No more in-model
  `cr.commit()`; no advisory locks; Odoo's HTTP retry wrapper works
  normally.
- **Observability improves.** Failures persist as inbox rows with
  `last_error` and can be retried from the admin UI via `action_retry`.
  Before this change, a failed CDR was only visible in the log.
- **CDR payloads are now replayable.** The raw XML is kept in the
  inbox until vacuumed, so on-call engineers can reproduce a
  problematic case without live FreeSWITCH traffic.
- The webhook endpoint is still `auth='public'` — the separate P0
  finding §1.1 in `ANALYSIS.md` about webhook authentication is
  unchanged by this ADR and remains open.

## Touched files

- `connect_freeswitch/models/cdr_inbox.py` — new model + cron methods
- `connect_freeswitch/models/__init__.py` — registers the model
- `connect_freeswitch/data/cdr_inbox_cron.xml` — three `ir.cron`
  entries (`process_pending`, `reap_stuck`, `vacuum`)
- `connect_freeswitch/views/cdr_inbox_views.xml` — admin list/form +
  menu
- `connect_freeswitch/security/access_rules.xml` — admin / user /
  webhook ACLs for the inbox model
- `connect_freeswitch/controllers/freeswitch_cdr.py` — replaced inline
  parsing + `on_freeswitch_cdr` dispatch with `inbox.receive(payload)`;
  XML parsing relocated to the inbox model
- `connect_freeswitch/models/call.py` — removed advisory lock and
  manual commits from `on_freeswitch_cdr`; renamed
  `_process_cdr_locked` → `_process_cdr`
- `connect_freeswitch/__manifest__.py` — version `19.0.1.7.10` →
  `19.0.1.8.0`; new data files registered
