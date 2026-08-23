# Payment-Behavior Digest

Beyond the per-record events, the module runs a scheduled job that produces a
periodic **payment-behavior observation** per customer — a rolled-up view of how
promptly a commercial partner pays. This gives the memory engine a stable signal
(average / maximum days late, share of late invoices) without replaying every
individual payment.

## The scheduled job

| Property | Value |
|----------|-------|
| Cron name | **Memory Sale: Payment Behavior Digest** |
| XML id | `connect_memory_sale.digest_cron_payment_behavior` |
| Runs as | `base.user_root` (superuser) |
| Model / method | `res.partner._memory_sale_payment_digest()` |
| Interval | Every **1 hour** |

The cron is created with `noupdate="1"`, so once installed you can freely change
its interval or deactivate it in **Settings ▸ Technical ▸ Scheduled Actions**
without a module upgrade overwriting your change.

## What one run does

Each run processes **one batch** of eligible customers:

1. If the Memory master switch is off, it returns immediately.
2. It finds commercial partners with posted customer invoices/refunds
   (`out_invoice` / `out_refund`) in `paid`, `in_payment`, or `partial` state
   dated within the last *N* months (`digest_period_months`).
3. It keeps only partners whose digest cursor
   (`res.partner.memory_payment_digest_date`) is **stale** — older than 7 days or
   never run — and who are **external**, then takes the first `digest_batch_size`
   of them.
4. For each such partner it loads the qualifying invoices for the period:
    - If there are **fewer than** `digest_min_invoices`, it just advances the
      partner's cursor and emits nothing (not enough signal).
    - Otherwise it computes, over the reconciled payments: average days late,
      maximum days late, and the ratio / percentage of invoices paid late, then
      emits one `kind="observation"` event (`domain="account"`) and advances the
      cursor.

Because the cursor advances on every processed partner, the hourly cron walks
through the customer base in batches and re-visits each partner at most once
every 7 days.

## The observation event

- **text** — e.g. `Acme Corp: 8 invoices in 6 months (12400 EUR). Avg 5 days late, 38% paid late, max 21 days.`
- **data** — `period_months`, `invoices_count`,
  `total_amount_company_currency`, `currency`, `avg_days_late`, `max_days_late`,
  `late_count`, `late_ratio`
- **tags** — `domain:account`, `role:customer`, `commercial:<partner_id>`,
  `signal:late_payment`, `kind:digest`
- **dedup_key** — `payment-digest-<partner_id>-<ISO-year>W<ISO-week>` (at most one
  digest per partner per ISO week, so mid-week reruns collapse)

## Configuration parameters

The digest reads three `ir.config_parameter` knobs, seeded at install
(`data/memory_sale_data.xml`, `noupdate="1"`). Edit them under **Settings ▸
Technical ▸ System Parameters** (Connect Administrator / technical access).

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `connect_memory_sale.digest_period_months` | `6` | Look-back window, in months, for qualifying invoices and the lateness stats. |
| `connect_memory_sale.digest_min_invoices` | `3` | Minimum qualifying invoices before a partner produces a digest; below this the cursor is advanced with no event. |
| `connect_memory_sale.digest_batch_size` | `50` | Maximum partners processed per hourly run. |

!!! tip "Tuning throughput"
    On a large customer base, raise `digest_batch_size` (or shorten the cron
    interval) so every eligible partner is revisited within the 7-day staleness
    window. Lower it if the hourly run competes with other load. Amounts are
    summed in the **company currency** (`amount_total_signed`).
