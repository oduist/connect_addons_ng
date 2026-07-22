# Connect Memory — Sale & Payment Behavior Specification

## Module Info

- **Name:** Connect Memory — Sale & Payment Behavior
- **Technical:** `connect_memory_sale`
- **Version:** 19.0.1.0.0
- **Depends:** `connect_memory`, `sale`, `account`
- **Python deps:** none
- **Application:** False
- **License:** Other proprietary
- **post_init_hook:** `post_init_hook` (starts the trial clock, refreshes the Connect license)

## Overview

`connect_memory_sale` is a **domain module** on top of `connect_memory`
(ADR-043): it feeds sales and finance activity into the same outbox/inbox
contract. It captures sale-order lifecycle, posted invoices/refunds, customer
payments, and an hourly per-customer payment-behavior digest. Like the base
module, **capture never breaks the host operation** — every path snapshots
before `super()` and wraps emission in `try/except` — and every emit goes through
`connect.memory.mixin._memory_emit(..., module="connect_memory_sale")`, so it is
gated by the master switch and its own Connect license.

Registers `"connect_memory_sale"` in
`odoo.addons.connect.models.license.ODUIST_MODULES`.

All events use `sensitivity="financial"` and `domain` in (`sale`, `account`).

---

## Models

### `connect.memory.sale.mixin` (AbstractModel) — models/memory_sale_mixin.py

Shared envelope builders for all sale paths:
- `_memory_sale_should_capture(partner)` — single gate: master switch on **and**
  `partner` external (delegates to `mail.thread._memory_is_external`).
- `_memory_sale_base_tags(domain, role, commercial_id)` → `domain:` / `role:` /
  `commercial:` tags.
- `_memory_sale_build(*, domain, kind, scope, source, text, tags, sensitivity,
  dedup_key, facts=None, data=None)` — full envelope dict (`event_version=1`,
  `occurred_at`, `actor={type:system, ref:odoo}`, `content_hash`).
- `_memory_sale_scope(record, partner)` / `_memory_sale_source(record)` —
  commercial-partner scope and the `source` block (system/db/company/model/res_id/url).
- `_memory_sale_content_hash(text)` — `sha256:` helper.

### `sale.order` (extension) — models/sale_order.py

Tracked scalars: `amount_total`, `amount_untaxed`, `currency_id`, `date_order`,
`validity_date`, `commitment_date`, `partner_shipping_id`. Tracked line fields:
`product_uom_qty`, `price_unit`, `discount`, `price_subtotal`.

- **`create`** → `created` event (`domain=sale`), text summarizing lines,
  `data={amount_total, currency, lines}`, `dedup_key=sale.order-<id>@created`.
- **`write`** — snapshots tracked scalars/lines **before** `super().write()`,
  then:
  - `state=='sale'` → `lifecycle` "confirmed"; `state=='cancel'` → "cancelled";
    `locked is True` → "locked" (`dedup_key=sale.order-<id>@<label>`).
  - otherwise, on an order already in `sale` → `state_change` (renegotiation):
    diff of tracked scalars + a parsed `order_line` o2m diff (update/add/delete),
    `tag signal:renegotiation`, `dedup_key=sale.order-<id>@edit-<timestamp>`.

### `account.move` (extension) — models/account_move.py

`action_post` → `posted` event for `out_invoice` / `out_refund` / `in_invoice` /
`in_refund` (`role` customer/vendor, `domain=account`, `kind=lifecycle`,
`dedup_key=account.move-<id>@posted`), `data` with move type, totals, due date,
payment state.

### `account.partial.reconcile` (extension) — models/account_partial_reconcile.py

`create` → a payment event per reconcile touching a customer/vendor invoice.
Picks the real invoice over a refund, computes `days_late` from `max_date` vs
`invoice_date_due`, adds `signal:late_payment` when late
(`kind=lifecycle`, `dedup_key=account.partial.reconcile-<id>`), `data` with
amount, currency, payment date, days late, invoice ref.

### `res.partner` (extension) — models/res_partner.py

- `memory_payment_digest_date` (Datetime, indexed) — staleness cursor.
- `_memory_sale_payment_digest()` (cron) — for a batch of commercial partners
  with paid invoices in the period whose digest is stale (> 7 days / never) and
  who are external: emit one `observation` (`domain=account`) with avg/max days
  late and late ratio over the last N months, then advance the cursor. Partners
  with fewer than `digest_min_invoices` just get their cursor advanced.

## Security

No new `ir.model.access` rows — the module only extends `sale.order`,
`account.move`, `account.partial.reconcile` and `res.partner` (governed by their
own access) and reuses `connect.memory.outbox`/`connect.memory.inbox` from the
base module.

## Data / crons — data/memory_sale_data.xml

- `digest_cron_payment_behavior` — hourly `res.partner._memory_sale_payment_digest()`.
- Three `ir.config_parameter` knobs: `connect_memory_sale.digest_period_months`
  (6), `connect_memory_sale.digest_min_invoices` (3),
  `connect_memory_sale.digest_batch_size` (50).

## Tests — tests/

`test_sale_capture`, `test_invoice_capture`, `test_payment_capture`,
`test_payment_digest`.
