# Oduist Connect Memory — Sale & Payment Behavior — Administrator Guide

`connect_memory_sale` is a **domain module** on top of `connect_memory`
(ADR-043). It feeds sales and finance activity into the same external-memory
pipeline: it captures sale-order lifecycle, posted invoices and refunds, customer
and vendor payments, and an hourly per-customer payment-behavior digest.

The module holds **no configuration of its own**. Every event it produces is
handed to `connect_memory` through
`connect.memory.mixin._memory_emit(..., module="connect_memory_sale")`, which
enqueues it on the shared **outbox** (`connect.memory.outbox`). An external
memory engine (Hindsight / Cognee) pulls the outbox and pushes results back into
the inbox — Odoo never calls the engine directly. See the **Memory** module
documentation (`connect_memory`) for the outbox/inbox contract, the master
switch, and the sidecar.

!!! info "Capture never breaks the host operation"
    Every capture path snapshots the record **before** `super()` and wraps
    emission in `try/except` (ADR-009). A failure to build or enqueue a memory
    event is logged and swallowed — it can never roll back a sale order,
    invoice posting, or payment reconciliation.

## What this module captures

| Trigger | Odoo model | Event `domain` / `kind` |
|---------|------------|-------------------------|
| Sale order created | `sale.order` (`create`) | `sale` / `created` |
| Sale order confirmed, cancelled, locked | `sale.order` (`write`) | `sale` / `lifecycle` |
| Confirmed sale order edited (renegotiation) | `sale.order` (`write`) | `sale` / `state_change` |
| Invoice / refund posted (customer or vendor) | `account.move` (`action_post`) | `account` / `lifecycle` |
| Payment reconciled against an invoice | `account.partial.reconcile` (`create`) | `account` / `lifecycle` |
| Hourly payment-behavior digest per customer | `res.partner` (cron) | `account` / `observation` |

All events carry `sensitivity="financial"`. See [Captured Events](events.md) for
the details of each path and [Payment-Behavior Digest](payment-digest.md) for the
scheduled job and its tuning parameters.

## Dependencies

From `__manifest__.py`:

| Dependency | Why |
|------------|-----|
| `connect_memory` | Provides the master switch, the `connect.memory.mixin` emit path, and the outbox/inbox transport. |
| `sale` | Host app for the `sale.order` capture. |
| `account` | Host app for the `account.move` and `account.partial.reconcile` capture. |

`application` is `False` — this is a bridge/domain add-on, not a standalone app.
The module registers `connect_memory_sale` in Connect's licensed-module registry
(`ODUIST_MODULES`), so it is enforced by its **own** Connect license; the
`post_init_hook` starts the trial clock and refreshes the license at install.

## Prerequisites

- A running Odoo instance with `connect`, `connect_memory`, `sale`, and
  `account` installed.
- The **Memory master switch** turned on in the `connect_memory` settings
  (`memory_enabled`). While it is off, `_memory_enabled()` returns false and
  **nothing** is captured — every path checks it first.
- A valid Connect license for `connect_memory_sale` (silent gate: a license
  failure degrades to "allow" so capture never blocks the business operation,
  but events are dropped when the license check returns false).
- The external memory engine configured on the `connect_memory` side to drain the
  outbox. This module only produces events; it does not talk to the engine.

## What gets captured — the external-party gate

Every path runs through a single gate, `_memory_sale_should_capture(partner)`,
which requires **both**:

1. the master switch is on, and
2. the partner is **external** — a real third party, not one of our own
   companies and not an internal employee (a partner linked to a non-share
   user). This delegates to `mail.thread._memory_is_external`.

Orders, invoices and payments for internal partners are silently skipped.

## Security

This module adds **no new `ir.model.access` rows and no new menus**. It only
extends existing models (`sale.order`, `account.move`,
`account.partial.reconcile`, `res.partner`), which stay governed by their own
Sales / Accounting access rights, and it reuses the `connect.memory.outbox` and
`connect.memory.inbox` models owned by `connect_memory`.

The one new field, `res.partner.memory_payment_digest_date`, is an internal
staleness cursor for the digest cron; it is not surfaced in any dedicated view.

!!! note "Master switch and menus live in connect_memory"
    There is no `connect_memory_sale` submenu. Enable/disable capture and inspect
    the outbox/inbox from the **Memory** screens provided by `connect_memory`
    (under the Connect app). The security convention across Connect —
    `connect.group_user` (read), `connect.group_admin` (full CRUD),
    `connect.group_webhook` (webhooks) — is applied by the base module on those
    shared models.

## Guide contents

1. [Captured Events](events.md) — sale, invoice and payment capture in detail.
2. [Payment-Behavior Digest](payment-digest.md) — the hourly cron and its
   configuration parameters.
