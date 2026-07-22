# 043 — External AI memory via an outbox/inbox pull contract (`connect_memory`)

## Status

Accepted

## Context

Connect should give Odoo a durable, queryable "memory" of each customer —
correspondence and business events — that an AI engine (Hindsight, Cognee, …)
can summarize and answer questions against. Two forces shape the design:

1. **We do not want to couple Odoo to any one memory engine.** Engines differ in
   API, ingestion model and availability; embedding one in Odoo would make the
   integration brittle and hard to swap.
2. **Capture must be free and safe.** Emitting a memory event must never slow
   down or break the business operation that triggered it (posting an invoice,
   sending a message), and backfilling years of history must not RS256-verify a
   license per event.

The modules already exist and are proven in the legacy `connect_addons` repo;
this ADR records the design as they are ported into `connect_addons_ng`.

## Options considered

- **A. Odoo calls the engine directly** (synchronous or via a queue job).
  Simplest to reason about, but couples Odoo to one engine's API, puts engine
  latency/outages on the critical path of business writes, and needs per-engine
  code in Odoo.
- **B. Outbox/inbox pull contract.** Odoo writes engine-neutral events into an
  `outbox` table and questions into an `inbox` table; an external per-engine
  sidecar pulls, loads, acks and answers. Odoo never calls the engine.
- **C. A message bus** (Kafka/Redis/AMQP) between Odoo and the engine. Most
  scalable, but adds heavy infrastructure and an operational dependency that is
  overkill for this workload and hard to ship to customer installs.

## Decision

Adopt **option B**. Concretely:

1. **Two JSON tables own the contract.** `connect.memory.outbox` holds outgoing
   engine-neutral events (a JSON `payload` envelope per row);
   `connect.memory.inbox` holds reflect/recall requests and their answers. The
   envelope schema (event_id, source, domain, kind, scope, actor, text, tags,
   sensitivity, dedup_key, content_hash) is engine-agnostic — the sidecar
   decides how to load it.
2. **Odoo emits, never calls.** A token-protected JSON-RPC pull API
   (`/connect_memory/outbox/{fetch,ack}`, `/connect_memory/inbox/{fetch,answer}`)
   lets the sidecar drive the exchange; Odoo opens no outbound connection to the
   engine. An external gateway (`deploy/hindsight_gateway.py`) is the reference
   sidecar.
3. **Capture is best-effort and idempotent.** Every capture path is wrapped in
   `try/except`; `enqueue` deduplicates on `(dedup_key, content_hash)` and an
   edit produces a new event. A per-`(day, module)` ormcached Connect-license
   gate keeps backfill cheap and degrades to "allow" on any error, so capture
   can never break the host write.
4. **Base vs domain modules.** `connect_memory` (base) captures only real
   external correspondence (`mail.thread.message_post` on any document). Business
   events live in domain modules — `connect_memory_sale` (sale/invoice/payment +
   payment-behavior digest), and future `connect_memory_crm` — each depending on
   the base, registered in `ODUIST_MODULES` and licensed independently.
5. **Retention keeps a tombstone.** A daily cron drops the bulky `payload` of
   sent rows past a retention window but keeps the `(dedup_key, content_hash)`
   tombstone, so re-emits stay deduplicated. The memory itself lives in the
   engine; the payload is only a transport buffer.

*Rejected:* A (engine coupling + latency on business writes), C (bus
infrastructure disproportionate to the workload and awkward to ship on-prem).

## Consequences

- New modules `connect_memory` (19.0.1.0.1, `depends: ['connect']`, application)
  and `connect_memory_sale` (19.0.1.0.0, `depends: ['connect_memory','sale','account']`).
- A memory install needs an external sidecar deployed from
  `connect_memory/deploy/` and a shared `memory_service_token` set in
  Connect → Settings → Memory; without it, events simply accumulate in the
  outbox.
- Security follows repo convention: `connect.group_user` reads the outbox
  (read + create on the inbox), `connect.group_admin` full CRUD, backfill
  job/wizard admin-only.
- Adding a new memory source is a new domain module, not a change to the base —
  the envelope and pull contract stay fixed.
