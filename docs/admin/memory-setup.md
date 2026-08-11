# Customer Memory

The `connect_memory` module gives Odoo a durable, external **AI memory** of
each customer — correspondence and business events that an AI engine
(Hindsight, Cognee, …) can summarize and answer questions against. Install the
optional `connect_memory_sale` module to also feed sale orders, invoices and
payments into that memory.

## How it works

Odoo never talks to the memory engine directly. It writes engine-neutral events
into an **outbox** table (`connect.memory.outbox`) and questions into an
**inbox** table (`connect.memory.inbox`). An external per-engine **gateway**
(shipped in `connect_memory/deploy/`) *pulls* pending events over HTTP, loads
them into the brain, acknowledges them, and writes answers back.

Because Odoo only emits events, capture is fast and can never break the business
operation that triggered it. If no gateway is deployed, events simply accumulate
in the outbox until one starts pulling.

## 1. Install the modules

Install `connect_memory` like any Odoo addon. Add `connect_memory_sale` if you
want sale/invoice/payment events and the payment-behavior digest.

## 2. Configure Connect → Configuration → Memory

| Setting | Meaning |
|---------|---------|
| Enable memory capture | Master switch — nothing is captured while off |
| Memory service URL | Base URL of your external gateway (informational) |
| Memory service token | Shared secret the gateway uses to authenticate its pull requests |
| Default engine | Engine label put on new requests (default `hindsight`) |
| Outbox retention (days) | A daily cron drops the bulky payload of *sent* rows older than this, keeping a de-dup tombstone. `0` = keep payloads |

## 3. Deploy the gateway

The reference gateway lives in `connect_memory/deploy/`
(`hindsight_gateway.py`, `Dockerfile`, `docker-compose.yml`,
`requirements.txt`, `SETUP.md`). Copy `.env.example` → `.env`, set your Odoo URL
and the **same** memory service token you entered in step 2, and start it with
Docker Compose. The real `.env` is never committed.

The gateway authenticates every call with the token (as the `token` JSON-RPC
param or the `X-Memory-Token` header) against these routes:

| Route | Purpose |
|-------|---------|
| `POST /connect_memory/outbox/fetch` | pull pending events |
| `POST /connect_memory/outbox/ack` | acknowledge processed events |
| `POST /connect_memory/inbox/fetch` | claim pending questions |
| `POST /connect_memory/inbox/answer` | write an answer back |

## 4. Backfill history (optional)

Newly captured correspondence flows automatically once the switch is on. To load
**existing** history:

- **One customer** — open a partner and click **Load correspondence to memory**;
  it queues that customer's past emails and chatter messages (idempotent, so a
  second click reports "0 new").
- **All customers** — Connect → Configuration → Memory → **Backfill all
  partners** opens a wizard: pick a date range, preview the candidate count, and
  start a resumable background job that a cron drains in batches.

## Security

- **Connect Users** can read outbox events (and see the partner *Memory* smart
  button) and create inbox questions.
- **Connect Admins** have full access, including the backfill jobs and wizard
  (admin-only infrastructure).
