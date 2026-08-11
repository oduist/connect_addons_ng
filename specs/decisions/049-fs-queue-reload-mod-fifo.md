# ADR-049: Refresh mod_fifo when an FS Queue changes

**Status:** Accepted
**Date:** 2026-06-25
**Issue:** Linear ODU-44
**Relates to:** [ADR-013](013-freeswitch-fifo-queues.md) (mod_fifo), [ADR-048](048-fs-queue-fallback-fs-fifo-handle.md)

## Context

mod_fifo loads its outbound `<member>` consumers from `fifo.conf.xml` (served by
`connect_freeswitch` via xml_curl) **only at module (re)load**. When a queue's members
or `max_wait_time` change in Odoo, the generated `fifo.conf` changes but FreeSWITCH keeps
the **stale** list — so `fifo list` shows `outbound_per_cycle=0`, mod_fifo never originates
the agent, and the caller waits in silence. Reproduced live (ODU-44): a member added in
Odoo only started ringing after a manual `fs_cli -x "reload mod_fifo"`.

## Decision

When a `connect.fs_fifo` is created/written (members/`max_wait_time`) or unlinked, Odoo
issues `freeswitch_api('reload', 'mod_fifo')` (verified: a single call re-reads XML via
xml_curl, no separate `reloadxml` needed).

**Timing — after commit.** The reload is scheduled on `cr.postcommit`, not run inline:
FreeSWITCH re-fetches `fifo.conf` over xml_curl on a **separate** connection, so it must run
**after** Odoo commits or it would read the pre-change data. The callback is **deduped per
transaction** (one reload regardless of how many queues/writes), and **best-effort**
(`try/except` + log) so a save never fails because FreeSWITCH is unreachable.

Only fifo.conf-affecting fields trigger it (`member_user_ids`, `member_endpoint_ids`,
`max_wait_time`). Per-call dialplan fields (MoH, timeout action, recording) are fetched fresh
via xml_curl on every call and need no reload.

## Consequences

- Editing a queue's agents in the UI takes effect on the next call with no manual step.
- A brief module reload on each queue change; negligible at human edit rates, and deduped.
- No schema change, no migration. ODU-43 (reachability) + ODU-44 (this) together make the
  FS Queue work end-to-end.
