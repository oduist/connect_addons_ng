# Connect Memory Module Specification

## Module Info

- **Name:** Connect Memory
- **Technical:** `connect_memory`
- **Version:** 19.0.1.0.1
- **Depends:** `connect`
- **Python deps:** none
- **Application:** True
- **License:** Other proprietary
- **post_init_hook:** `post_init_hook` (starts the trial clock, refreshes the Connect license)

## Overview

`connect_memory` gives Odoo an **external, engine-neutral AI memory** (ADR-043).
Odoo is strictly an **event emitter**: it never calls a memory engine. It writes
neutral domain events into `connect.memory.outbox` (a JSON envelope per row); an
external per-engine sidecar **pulls** pending rows over HTTP, loads them into its
brain (Hindsight, Cognee, …) and **acks** them. Questions travel the other way:
Odoo writes a `pending` request into `connect.memory.inbox`, the sidecar claims
it, asks the engine and writes the answer back.

This base module is the **communications layer**: it captures real external
correspondence (emails / chatter comments with an external author or recipient)
on the chatter of *any* document via a `mail.thread.message_post` override.
Business events (orders, invoices, payments, …) are emitted by **domain
modules** (`connect_memory_sale`, and future `connect_memory_crm`), never here.

Design invariants:
- **Capture never breaks the host operation.** Every capture path is wrapped in
  `try/except` and the license gate degrades to "allow" on any error.
- **Idempotent.** `enqueue` deduplicates on `(dedup_key, content_hash)`; an
  edit (new `content_hash`) produces a new event.
- **Provider-neutral.** The envelope carries an optional `engine`; the sidecar,
  not Odoo, decides how to load it.
- **Byte-identical Python across series.** `memory_outbox.py` branches on
  `release.version_info[0] >= 19` for `models.Constraint` vs `_sql_constraints`;
  `controllers/main.py` branches the route type `json` vs `jsonrpc`.

Registers `"connect_memory"` in `odoo.addons.connect.models.license.ODUIST_MODULES`
so it is enforced by its own Connect license.

---

## Models

### `connect.memory.outbox` — models/memory_outbox.py

Engine-neutral domain events emitted by Odoo, pulled/acked by the sidecar.
`_order = "id asc"`.

| Field | Type | Notes |
|-------|------|-------|
| `event_id` | Char | Required, indexed, UUID default; `unique(event_id)` constraint |
| `dedup_key` | Char | Indexed; stable source id, e.g. `mail.message-42-c7` |
| `content_hash` | Char | `sha256:<hex>` of the event text; detects edits |
| `domain` | Char | Required, indexed; data domain (`partner`, `sale`, `account`, …) |
| `kind` | Char | Required; event kind (`message`, `observation`, `state_change`, `lifecycle`, …) |
| `payload` | Text | JSON envelope; **cleared** by the retention cron once sent (dedup tombstone kept) |
| `state` | Selection | `pending` / `sent` / `failed`; default `pending`, indexed |
| `engine` | Char | Optional target engine |
| `company_id` | Many2one res.company | Indexed |
| `commercial_partner_id` | Many2one res.partner | Indexed; memory is aggregated by commercial partner |
| `res_model` / `res_id` | Char / Integer | Source record, indexed |
| `sent_at` | Datetime | Set on ack |
| `attempts` | Integer | Failed-ack counter |
| `last_error` | Text | Last failure detail |

Methods:
- `enqueue(envelope)` — create one row; idempotent on `(dedup_key, content_hash)`
  when both are set (an existing `pending`/`sent` row is returned unchanged).
- `fetch_batch(limit=100, domain=None, engine=None)` — return pending rows as
  dicts `{id, event_id, domain, kind, payload}`; engine filter matches the
  target engine **or** rows with no engine.
- `ack(ids, ok=True, error=None)` — mark `sent` (with `sent_at`) or `failed`
  (bump `attempts`, store `last_error`).
- `_cron_vacuum_sent(days=None)` — drop the bulky `payload` of `sent` rows older
  than `memory_outbox_retention_days`, keeping the dedup tombstone; `days=0`
  disables. The memory lives in the engine — payload is only a transport buffer.
- `_memory_content_hash(text)` — `sha256:` helper.

### `connect.memory.inbox` — models/memory_inbox.py

Questions to the engine and their answers. `_order = "id desc"`.

| Field | Type | Notes |
|-------|------|-------|
| `query_type` | Selection | `reflect` / `recall`; default `reflect` |
| `query` | Text | Required; the question |
| `request` | Text | Full JSON request for the sidecar |
| `engine` | Char | Optional target engine |
| `state` | Selection | `pending` / `processing` / `done` / `failed`; indexed |
| `answer` | Text | Raw JSON answer |
| `answer_text` | Text | Human-readable answer extracted from the JSON |
| `res_model` / `res_id` | Char / Integer | Originating record |
| `commercial_partner_id` | Many2one res.partner | Indexed |
| `company_id` / `requested_by` | Many2one | Defaults to current company / user |
| `done_at` | Datetime | Set on answer |

Methods: `submit(query, query_type, scope, res_model, res_id, engine)` (creates a
`pending` request); `claim_batch(limit=20, engine=None)` (flips to `processing`,
returns `{id, request}`); `store_answer(inbox_id, answer, ok=True)` (writes
`answer`/`answer_text`, sets `done`/`failed`).

### `connect.memory.mixin` (AbstractModel) — models/memory_mixin.py

Reusable helpers shared by the base and every domain module:
- `_memory_scope_for_partner(partner)` → `(scope, commercial)`; memory is keyed
  by `commercial_partner_id`, a specific contact carried as `partner_id`.
- `_memory_clean_body(html)` → plaintext.
- `_memory_enabled()` — master capture switch (`connect.settings.memory_enabled`),
  single source of truth.
- `_memory_emit(envelope, module="connect_memory")` — enqueue gated by the master
  switch **and** the Connect license of the owning module; domain modules pass
  their own name so each is licensed independently.
- `_memory_license_check_cached(date_key, module)` — `@tools.ormcache` gate keyed
  on `(day, module)`; re-evaluates an expiring trial within 24 h without an RS256
  verify per captured event (backfill replays hundreds of thousands of messages).
- `_memory_license_ok(module)` — never raises; any failure degrades to **allow**.

### `mail.thread` (override) — models/mail_thread.py

`message_post` captures real correspondence, never breaking the business op
(try/except). Capture rules (`_memory_should_capture`): `message_type` in
`("email", "comment")`, non-empty body, not an internal note (`mail.mt_note`),
model not in `EXCLUDED_MODELS = ("mail.channel",)`, and at least one **external**
partner on either end. `_memory_is_external` excludes internal employees (a
non-share user) and the company's own partners (`_memory_company_partner_ids`,
ormcached). `_memory_targets` resolves direction: external author → `in` to the
author's company; external recipients → `out` to each recipient's company.
`_memory_build_envelope` builds the `domain="partner", kind="message"` envelope
(scope, actor, text `[record] subject\nbody`, rich `tags`, `sensitivity="personal"`,
`dedup_key="mail.message-<id>-c<commercial>"`, `content_hash`).

### `connect.memory.backfill` + `connect.memory.backfill.wizard` — models/memory_backfill.py

Historical replay of all partners' correspondence into the outbox.
- `connect.memory.backfill` — a resumable job (`date_from`/`date_to`,
  `batch_size` default 500, `last_message_id` cursor, `state`
  running/done/cancelled, counters `estimate`/`processed`/`enqueued`/`skipped`).
  `_process_batch` scans `mail.message` after the cursor, replays via each
  record's `_memory_should_capture(enforce_enabled=False)` + `_memory_targets` +
  `_memory_build_envelope`, then `enqueue` (idempotent). `_cron_run` drains up to
  `batches_per_job=10` batches per running job, committing after each to stay
  resumable. Actions: `action_run_now`, `action_cancel`, `action_resume`.
- `connect.memory.backfill.wizard` (TransientModel) — `date_from` (default −6
  months), optional `date_to`, `batch_size`; `action_preview` counts candidates,
  `action_start` creates the job, runs the first batch synchronously and hands
  off to the cron.

### `res.partner` (extension) — models/res_partner.py

- `memory_event_count` (Integer, computed via `sudo()`) — outbox rows for the
  commercial partner; drives the smart button.
- `action_memory_events` — open the partner's outbox events (read-only list).
- `action_memory_backfill` — synchronous, idempotent per-partner backfill of the
  whole partner family's correspondence (limit 5000/run); returns a notification
  reporting `new / already / skipped`.
- `action_memory_summary` — submit a `reflect` request ("summary of what we know
  about this customer") into the inbox using `memory_default_engine`; opens the
  inbox record.

### `connect.settings` (extension) — models/settings.py

Fields: `memory_enabled` (Boolean master switch), `memory_service_url`,
`memory_service_token`, `memory_default_engine` (default `hindsight`),
`memory_outbox_retention_days` (default 7; `0` = keep payloads). Actions:
`open_memory_form` (standalone Memory settings form), `action_open_memory_backfill`
(opens the all-partners wizard).

---

## Controllers — controllers/main.py

HTTP (JSON-RPC) pull contract; the sidecar always initiates. Route type is
`json` on < 19 and `jsonrpc` on ≥ 19. All routes `auth="public"`,
`methods=["POST"]`, `csrf=False`, and token-protected: `memory_service_token`
passed as the `token` param **or** the `X-Memory-Token` header. On a bad token
they return `{"error": "unauthorized"}`.

| Route | Purpose | Returns |
|-------|---------|---------|
| `/connect_memory/outbox/fetch` | pull pending events (`limit`, `domain`, `engine`) | `{"events": [...]}` |
| `/connect_memory/outbox/ack` | ack processed events (`ids`, `ok`, `error`) | `{"acked": n}` |
| `/connect_memory/inbox/fetch` | claim pending requests (`limit`, `engine`) | `{"requests": [...]}` |
| `/connect_memory/inbox/answer` | write an answer (`id`, `answer`, `ok`) | `{"stored": bool}` |

---

## Security — security/ir.model.access.csv

| Model | `connect.group_user` | `connect.group_admin` |
|-------|----------------------|-----------------------|
| `connect.memory.outbox` | read | full CRUD |
| `connect.memory.inbox` | read + create | full CRUD |
| `connect.memory.backfill` | — (none) | full CRUD |
| `connect.memory.backfill.wizard` | — (none) | full CRUD |

Backfill job + wizard are infrastructure → admin-only. The `res.partner` memory
menu/smart-button are gated on `connect.group_user`; `memory_event_count`
computes via `sudo()`, so the field is safe for any internal user.

## Views

- `views/memory_outbox_views.xml`, `views/memory_inbox_views.xml`,
  `views/memory_backfill_views.xml` — list/form views for the three models.
- `views/res_partner_views.xml` — memory smart button + header actions on the
  partner form.
- `views/settings.xml` — standalone **Memory** settings form + settings menu
  (`connect.menu_connect_settings`, `connect.group_admin`).
- `views/memory_menus.xml` — **Memory** root menu (`connect.menu_connect_root`,
  `connect.group_user`, sequence 160) with **Outbox** / **Inbox** submenus.

## Data / crons — data/memory_data.xml

- `cron_memory_outbox_vacuum` — daily `_cron_vacuum_sent()`.
- `cron_memory_backfill` — every minute `_cron_run()` (drains running jobs).

## Deploy sidecar — deploy/

External pull-based gateway (`hindsight_gateway.py`) driving the Hindsight
engine: `Dockerfile`, `docker-compose.yml`, `requirements.txt`, `SETUP.md`,
`README.md`, `.env.example` (+ `.gitignore` ignoring the real `.env`). It polls
`/connect_memory/outbox/fetch`, loads events into the engine, `ack`s them, and
answers inbox requests via `/connect_memory/inbox/*`, authenticating with the
shared `memory_service_token`. No Docker image is built/pushed by the module;
the real `.env` is never committed.
