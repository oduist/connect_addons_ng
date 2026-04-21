# 013 — Serialize FreeSWITCH sibling-leg CDR processing

## Problem

`mod_xml_cdr` posts a separate CDR per channel. For a bridged call we get two
webhooks: one for the A-leg (caller channel) and one for the B-leg (callee
channel). `on_freeswitch_cdr` (connect_freeswitch/models/call.py) merges the
two legs into a single `connect.call` by searching for "orphan" channels whose
`parent_sid` matches the leg currently being processed.

When the call ends cleanly, FreeSWITCH delays the A-leg CDR by ~100 ms because
`hangup_after_bridge` and `record_session` run first, so the B-leg CDR always
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

Option 1. `pg_advisory_xact_lock` releases automatically on commit/rollback,
so a crashed worker cannot leave the key locked. Two subtle problems had to
be solved before it actually worked.

### Problem 1 — symmetric lock key

Tried `chain_key = cdr_data['other_leg_uuid'] or cdr_data['uuid']`. Turned out
non-symmetric: the parser fills `other_leg_uuid` from `odoo_parent_uuid` (set
on B-leg only, via `export nolocal:`) with fallback to FreeSWITCH's built-in
`Other-Leg-Unique-ID`. After hangup, the A-leg's CDR snapshot no longer
contains `Other-Leg-Unique-ID`, so A-leg ends up with empty `other_leg_uuid`
while B-leg has the A-leg's uuid → different chain keys → lock does nothing.

Tried `min(uuid, other_leg_uuid)`. Same problem: when A-leg's
`other_leg_uuid` is empty, `min` reduces to `uuid` while B-leg's `min` takes
the A-leg uuid. Asymmetric.

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

After the symmetric lock was in place the logs confirmed serialization
(second leg's `pg_advisory_xact_lock` waited ~50 ms for the first leg to
commit, and PostgreSQL txids were sequential). But the reverse-orphan
search on the second leg *still* returned empty, even via raw SQL on the
same cursor. The sibling row was committed in the DB (verified with an
out-of-band `psql` query) but invisible to the waiting leg.

Root cause: Odoo sets `ISOLATION_LEVEL_REPEATABLE_READ` on every
connection (`odoo/sql_db.py`). Under REPEATABLE READ, the transaction's
snapshot is taken at the first non-transaction-control statement. In our
case that statement was `SELECT pg_advisory_xact_lock(...)` itself —
snapshot frozen *before* the lock wait began. Acquiring the lock only
changes execution order, not snapshot visibility, so the waiting leg kept
seeing the pre-commit view of the world.

**Fix:** acquire the lock twice with a commit in between:

```python
self.env.cr.execute(
    "SELECT pg_advisory_xact_lock(hashtext(%s))", [chain_key])
self.env.cr.commit()
self.env.cr.execute(
    "SELECT pg_advisory_xact_lock(hashtext(%s))", [chain_key])
```

The first acquire serializes against any concurrent worker. When we get it,
the sibling has already committed. `commit()` releases our stale snapshot
(and the `xact_lock`). The second acquire starts a fresh transaction with
a new snapshot that includes the sibling's writes, and re-takes the lock.

For a 2-leg bridge the short window between the first commit and the
second acquire is safe: no third sibling can arrive for the same
`chain_id`, and any unrelated webhook hashes to a different key.

## Implementation

1. `connect_freeswitch/data/fs_templates.xml` — next to each
   `export nolocal:odoo_parent_uuid=${uuid}` (6 dialplan templates) add:
   ```xml
   <action application="export" data="odoo_chain_id=${uuid}"/>
   ```
2. `connect_freeswitch/controllers/freeswitch_cdr.py::_parse_cdr_xml` —
   extract the `odoo_chain_id` channel variable into `cdr_data['chain_id']`.
3. `connect_freeswitch/models/call.py::on_freeswitch_cdr` — at the top,
   before any mutation:
   ```python
   chain_key = cdr_data.get('chain_id') or cdr_data['uuid']
   self.env.cr.execute(
       "SELECT pg_advisory_xact_lock(hashtext(%s))", [chain_key])
   self.env.cr.commit()
   self.env.cr.execute(
       "SELECT pg_advisory_xact_lock(hashtext(%s))", [chain_key])
   ```

## Consequences

- Sibling CDRs are processed serially per bridge; unrelated calls are
  unaffected (different keys → no contention).
- `hashtext` collisions are possible but harmless: two unrelated bridges
  that happen to collide will briefly serialize.
- Single-leg CDRs (no bridge, no `odoo_chain_id` set) fall back to locking
  on their own uuid — trivially unique, no-op serialization.
- The intermediate `commit()` flushes any ORM work done earlier in the
  request. The CDR webhook does no pre-lock writes, so this is safe here;
  the pattern should not be copied blindly into controllers that have
  uncommitted state at that point.
- Requires the FS dialplan to be regenerated on deployed installations
  after the template change.
