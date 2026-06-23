# ADR-013: FIFO queues via mod_fifo with static consumers

**Status:** Accepted
**Date:** 2026-04-22

## Context

`connect_freeswitch` already supported ring groups (simultaneous bridge to several users via `connect.callflow.ring_users`) and IVR menus. What was missing was call-queue behaviour: holding the caller with Music-on-Hold while distributing the call to available agents and falling back to voicemail or another extension after a timeout.

The call flow we wanted to support:
- assign a queue as the destination of `connect.exten` (directly) or `connect.number` (a DID);
- offer a queue as a destination of an IVR choice;
- chain ring-users → queue → voicemail, so that if nobody in the ring group answered the caller is routed into the queue before voicemail;
- use a queue as the default destination of an IVR when no digit was collected.

Queue features are FreeSWITCH-specific and not a natural abstraction for Twilio, so the implementation must stay inside `connect_freeswitch` and not leak into the core.

## Options

1. **mod_callcenter** — a full-blown contact-centre module with agents (states, strategies, tiers), queue statistics, and its own persistent configuration (`callcenter.conf.xml`). Requires either generating that config at startup or pre-seeding it. Conceptually appealing but heavy: logged-in/paused states, agent presence and metric reporting imply a lot of extra UI and events we would then need to wire into Odoo. Overkill for the MVP.
2. **mod_fifo** — the small built-in FIFO module. No separate config file; a queue is created implicitly by name when the `fifo` app is first called. Provides MoH, position announcement, timeouts, caller exit key. Works either with "static" consumers (dialplan-driven) or dynamic ones registered from the outside.
3. **Pure dialplan** — simulate a queue with an enterprise `bridge` + MoH. Simpler still, but loses queue semantics entirely (no MoH interleaving, no pending-caller state, no clean timeout handling).

## Decision

Use **mod_fifo with static, dialplan-driven consumers**.

### How it works

When a call arrives at the queue extension:

1. The caller leg runs `<action application="fifo" data="fs_fifo_<id> in undef <moh> <timeout>"/>`, which parks the caller on the named queue with MoH and the configured max-wait timeout.
2. For every configured member (`connect.user` or `connect.endpoint`) the dialplan first issues `<action application="bgapi" data="originate {originate_timeout=<max_wait>}<dial_string> &amp;fifo(fs_fifo_<id> out nowait)"/>`. This starts each agent leg in the background; on answer the agent jumps into `fifo … out nowait` which pops a caller from the queue and bridges automatically.
3. The first agent to answer takes the call; the rest keep ringing until they time out or the caller is gone.
4. If the `fifo … in …` call returns without a bridge (timeout), `continue_on_fail=true` lets the dialplan continue to the timeout branch: hangup, voicemail, or transfer to a fallback extension.

This gives us the core queue behaviour (MoH, position announcement, timeout, fallback) without any extra FreeSWITCH config file.

### Why not dynamic consumers

Dynamic registration would let agents "log in" and "log out" of a queue at runtime, would allow paused/available/on-a-call states, and would decouple the queue entry dialplan from the member list. It also means real state to manage in both Odoo and FreeSWITCH and a richer UI. We defer all of that: the MVP is **static** — every configured member is tried on every queue call.

### Trade-offs accepted

- No online/offline/paused state for agents — all members are dialed every time.
- No aggregated queue statistics (wait time, abandoned rate, agent talk time) — only whatever mod_fifo events expose at call time.
- If all members are busy or unavailable the caller simply waits until `max_wait_time` then hits the timeout branch.

These are acceptable for the first cut. Dynamic consumer registration, stat collection, and richer routing strategies can be layered on later without changing the data model — the `connect.fs_fifo` record stays the single source of truth for queue configuration.

### Module placement

The new model is `connect.fs_fifo` (description "FS Queue") and lives entirely in `connect_freeswitch`. The core model `connect.exten.dst` Reference is extended via `selection_add`; `connect.number.destination` is extended the same way. `connect.callflow` gets a new `fs_fifo_id` field added via `_inherit` in the FreeSWITCH module. Core `connect` knows nothing about queues.

### Dockerfile / modules.conf

`mod_fifo` is not built by default in the project image. The Dockerfile module list and `autoload_configs/modules.conf.xml` are both updated to include `applications/mod_fifo`. A new image (bumped minor version) has to be built and pushed as part of this change.

## Consequences

- Admins get a new "FS Queues" menu to define queues (members, MoH, timeout, fallback).
- Callflows can chain `ring_users → queue → voicemail` and IVRs get a default branch when no digit is pressed.
- A queue can be the target of an IVR choice, the destination of a DID, or the direct target of any `connect.exten`.
- Rebuilding the FreeSWITCH image is required for the new backend to work (`mod_fifo` gets compiled in).
