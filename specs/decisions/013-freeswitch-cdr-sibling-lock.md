# 013 — Serialize FreeSWITCH sibling-leg CDR processing

> **Status: Superseded by [ADR-030](030-nleg-bridge-call-convergence.md).**
> The `pg_advisory_lock` / `chain_key` serialization described here was
> dropped during the `19.0` → `19.0-twilio-fs-compat` merge in favour of the
> post-commit `reconcile_bridge_link` N-leg convergence (ADR-030, which
> rejects the advisory lock as "Option C"). Kept for historical context.

## Problem

`mod_xml_cdr` posts a separate CDR per channel. For a bridged call we get two
webhooks: one for the A-leg (caller channel) and one for the B-leg (callee
channel). `on_freeswitch_cdr` (connect_freeswitch/models/call.py) merges the
two legs into a single `connect.call` by searching for "orphan" channels whose
`parent_sid` matches the leg currently being processed.

When the call ends cleanly, FreeSWITCH delays the A-leg CDR by ~100 ms because
`hangup_after_bridge` and `record_session` run first, so the B-leg CDR usually
commits before the A-leg CDR arrives. When the B-leg hangs up before answer
(fast-failed call), both CDRs land within ~20 ms. Odoo runs them on two
threaded workers in separate transactions: each sees its own channel but not
the sibling that the other worker hasn't committed yet → reverse-orphan search
returns empty → two `connect.call` rows remain in the DB.

## Options considered

1. **Postgres advisory lock keyed on a shared bridge identifier** at the start
   of `on_freeswitch_cdr`. Both legs must hash to the same key so the second
   worker waits until the first one commits and the reverse-orphan merge
   happens deterministically.
2. Unique index on `connect_channel.sid` + a retry/cron to re-run orphan
   merge. Requires new infrastructure and leaves a window where duplicate
   calls are visible in the UI.
3. Single-worker queue for CDR processing. Solves the race but changes
   deployment assumptions and adds latency.

## Decision

Option 1. Three subtle problems had to be solved before it actually worked
reliably under concurrent load.

### Problem 1 — symmetric lock key

Tried `chain_key = cdr_data['other_leg_uuid'] or cdr_data['uuid']`. Turned out
non-symmetric: the parser fills `other_leg_uuid` from `odoo_parent_uuid` (set
on B-leg only, via `export nolocal:`) with fallback to FreeSWITCH's built-in
`Other-Leg-Unique-ID`. After hangup, the A-leg's CDR snapshot no longer
contains `Other-Leg-Unique-ID`, so A-leg ends up with empty `other_leg_uuid`
while B-leg has the A-leg's uuid → different chain keys → lock does nothing.

**Fix:** add a dedicated dialplan variable `odoo_chain_id` exported **without**
`nolocal:`, so it is set locally on the A-leg and propagated to the B-leg
with the same value (the A-leg's uuid at bridge time). Both legs' CDRs carry
the identical `odoo_chain_id`, and the lock key is simply:

```python
chain_key = cdr_data.get('chain_id') or cdr_data['uuid']
```

`odoo_parent_uuid` stays as `nolocal:` — the parser still uses its presence
to distinguish A-leg vs B-leg when mapping `odoo_connect_user_id`.

### Problem 2 — REPEATABLE READ snapshot

With the symmetric key in place, `pg_advisory_xact_lock` serialized requests
(second leg's SELECT waited ~50 ms for the first leg to commit). But the
reverse-orphan search on the second leg *still* returned empty: the sibling
row was committed in the DB (verified with an out-of-band `psql` query) but
invisible to the waiting leg.

Root cause: Odoo sets `ISOLATION_LEVEL_REPEATABLE_READ` on every
connection (`odoo/sql_db.py`). Under REPEATABLE READ, the transaction's
snapshot is taken at the first non-transaction-control statement. In our
case that statement was `SELECT pg_advisory_*_lock(...)` itself — snapshot
frozen *before* the lock wait began. Acquiring the lock only changes
execution order, not snapshot visibility.

**Fix:** session-scoped `pg_advisory_lock` + commit after acquiring. The
session-scoped variant persists across transaction boundaries, so we can
commit the "acquire" transaction (discarding the stale snapshot) while
keeping the lock held. The next statement starts a fresh transaction with
a new snapshot that sees the sibling's committed writes.

### Problem 3 — commit before unlock

With session-scoped lock + post-acquire commit, concurrent stress tests
still produced duplicates. Logs showed the lock was acquired and waited
correctly, but the second leg still didn't see the first leg's channel.

Root cause: our `finally` block released the lock *before* the http
handler's outer commit had flushed our own writes. The sibling immediately
acquired the lock, committed its own (empty) acquire-tx, and took a fresh
snapshot — which still predated our pending commit.

**Fix:** commit our work inside `on_freeswitch_cdr` before releasing the
lock. The lock is held across the commit, so no sibling can snapshot
before our writes are durable.

## Implementation

1. `connect_freeswitch/data/fs_templates.xml` — next to each
   `export nolocal:odoo_parent_uuid=${uuid}` (6 dialplan templates) add:
   ```xml
   <action application="export" data="odoo_chain_id=${uuid}"/>
   ```
2. `connect_freeswitch/controllers/freeswitch_cdr.py::_parse_cdr_xml` —
   extract the `odoo_chain_id` channel variable into `cdr_data['chain_id']`.
3. `connect_freeswitch/models/call.py::on_freeswitch_cdr` — split into an
   outer method that owns the lock and an inner `_process_cdr_locked`
   that does the actual CDR processing:
   ```python
   chain_key = cdr_data.get('chain_id') or cdr_data['uuid']
   self.env.cr.commit()  # drop stale snapshot from controller entry
   self.env.cr.execute(
       "SELECT pg_advisory_lock(hashtext(%s))", [chain_key])
   self.env.cr.commit()  # end the acquire-tx so the next read is fresh
   self.env.invalidate_all()  # flush ORM caches tied to the old snapshot
   try:
       result = self._process_cdr_locked(cdr_data)
       self.env.cr.commit()  # commit BEFORE unlocking
       return result
   finally:
       self.env.cr.execute(
           "SELECT pg_advisory_unlock(hashtext(%s))", [chain_key])
   ```

## Verification

A stress test (`/tmp/stress_cdr.py`) fires N bridges in parallel, each as
two sibling CDRs with randomized arrival order and jitter. After the run:

- `SELECT COUNT(*) FROM connect_call` should equal N.
- `SELECT COUNT(*) FROM connect_channel` should equal 2·N.
- `SELECT COUNT(*) FROM connect_channel WHERE parent_sid IS NOT NULL AND
  parent_channel IS NULL` should be 0.

At 20 concurrent bridges the fix produced 20/40/0 — correct. At 30+ the DB
connection pool (default 64) is exhausted before the lock logic runs; that
is an orthogonal limit, not a concurrency bug, and realistic CDR traffic
never approaches it (CDRs fire at call end, not at call start).

## Consequences

- Sibling CDRs are processed serially per bridge; unrelated calls are
  unaffected (different keys → no contention).
- `hashtext` collisions are possible but harmless: two unrelated bridges
  that happen to collide will briefly serialize.
- Single-leg CDRs (no bridge, no `odoo_chain_id` set) fall back to locking
  on their own uuid — trivially unique, no-op serialization.
- The session-scoped lock is explicitly released in `finally`. Even on
  exception the lock is freed before the pooled connection is returned.
- The pre-lock `commit()` flushes any ORM work done earlier in the request.
  The CDR webhook does no pre-lock writes, so this is safe here; the
  pattern should not be copied blindly into controllers that have
  uncommitted state at that point.
- Requires the FS dialplan to be regenerated on deployed installations
  after the template change.
