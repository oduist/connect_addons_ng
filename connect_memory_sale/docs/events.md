# Captured Events

Each capture path builds an event envelope with
`connect.memory.sale.mixin._memory_sale_build(...)` and enqueues it via
`connect.memory.mixin._memory_emit(envelope, module="connect_memory_sale")`. The
envelope schema (`event_version`, `occurred_at`, `actor`, `text`, `facts`,
`data`, `tags`, `sensitivity`, `dedup_key`, `content_hash`) is defined by
`connect_memory`. Every event here uses `sensitivity="financial"` and a `scope`
built around the customer's **commercial partner** (plus the specific contact
when different).

!!! info "Deduplication"
    Each event carries a stable `dedup_key` so the memory engine can collapse
    replays. Lifecycle transitions key on the record and the transition label;
    only free-form edits (`state_change`) key on a timestamp.

## Sale orders — `sale.order`

Tracked scalar fields: `amount_total`, `amount_untaxed`, `currency_id`,
`date_order`, `validity_date`, `commitment_date`, `partner_shipping_id`.
Tracked order-line fields: `product_uom_qty`, `price_unit`, `discount`,
`price_subtotal`.

=== "Created"

    On `create`, a `kind="created"` event (`domain="sale"`) summarizing the
    order lines.

    - **text** — e.g. `S00021 created for Acme Corp: 3 x Product A, 1 x Product B`
    - **data** — `amount_total`, `currency`, and a `lines` list
      (product, qty, uom, price_unit, discount, subtotal)
    - **tags** — base tags + `stage:draft`, `via:sale.order`, `res:sale.order-<id>`
    - **dedup_key** — `sale.order-<id>@created`

=== "Lifecycle"

    On `write`, a `kind="lifecycle"` event when a state transition is detected:

    | Condition in `vals` | Label | dedup_key |
    |---------------------|-------|-----------|
    | `state == 'sale'` | `confirmed` | `sale.order-<id>@confirmed` |
    | `state == 'cancel'` | `cancelled` | `sale.order-<id>@cancelled` |
    | `locked is True` | `locked` | `sale.order-<id>@locked` |

    - **data** — `amount_total`, `currency`
    - **tags** — base tags + `outcome:<label>`, `via:sale.order`,
      `res:sale.order-<id>`

=== "State change (renegotiation)"

    On `write` to an order **already in `sale` state** that is not itself a
    lifecycle transition, a `kind="state_change"` event capturing what changed.
    Tracked scalars are snapshotted **before** `super().write()`; the order-line
    o2m command list is parsed into per-line add / update / delete diffs.

    - **text** — e.g. `Sale order S00021 (Acme Corp) edited: amount_total: 900.0 -> 1100.0; Product A.price_unit: 300 -> 350`
    - **data** — `{"changes": {...}}` with old→new pairs per field and per line
    - **tags** — base tags + `signal:renegotiation`, `via:sale.order`,
      `res:sale.order-<id>`
    - **dedup_key** — `sale.order-<id>@edit-<timestamp>`

## Invoices & refunds — `account.move`

On `action_post`, a `kind="lifecycle"` event (`domain="account"`) for moves of
type `out_invoice`, `out_refund`, `in_invoice`, or `in_refund`. Other move types
(journal entries, etc.) are ignored.

- **role** — `vendor` for `in_*` move types, otherwise `customer`
- **text** — e.g. `Invoice INV/2026/0007 posted for Acme Corp: 1100.00 EUR due 2026-09-10.`
  (refunds are labelled `Credit Note / Refund`)
- **data** — `move_type`, `amount_total`, `amount_total_signed`,
  `company_currency`, `invoice_date_due`, `payment_state`
- **tags** — base tags + `move_type:<type>`, `via:account.move`,
  `res:account.move-<id>`
- **dedup_key** — `account.move-<id>@posted`

## Payments — `account.partial.reconcile`

On `create` of a partial reconcile, a `kind="lifecycle"` event
(`domain="account"`) for each reconcile that touches a customer or vendor
invoice/refund. When both sides are documents, a real invoice
(`out_invoice`/`in_invoice`) is preferred over a refund.

Lateness is computed from the reconcile's `max_date` versus the invoice's
`invoice_date_due`; when the payment lands after the due date the event adds a
`signal:late_payment` tag and reports the day count.

- **text** — e.g. `Invoice INV/2026/0007 (Acme Corp) received payment 1100.00 EUR on 2026-09-14 (4 days late).`
- **data** — `amount`, `company_currency`, `payment_date`, `days_late`,
  `invoice_ref`, `invoice_id`
- **tags** — base tags + `kind:payment`, `via:account.partial.reconcile`,
  `res:account.partial.reconcile-<id>` (+ `signal:late_payment` when late)
- **dedup_key** — `account.partial.reconcile-<id>`

!!! tip "Troubleshooting missing events"
    If an expected event never reaches the outbox, check, in order: the Memory
    master switch is on; the partner is **external** (not an internal user, not
    one of your own companies); the `connect_memory_sale` license is valid; and
    the module logger `connect_memory_sale` for a swallowed capture exception
    (e.g. `memory_sale: sale write capture failed`).
