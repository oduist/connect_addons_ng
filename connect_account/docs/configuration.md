# Configuration & Usage

The Accounting bridge has **no settings of its own**. Once installed, it works
automatically. This page explains how the automatic linking behaves and the two
shared settings that influence it.

## How invoices are matched

Matching runs inside `connect.call.process_call_event()` — the hook every provider
calls when a call is created — right after the core has recorded the call and
resolved its partner:

1. If the call already has a linked invoice, nothing happens (a manual assignment is
   never overwritten).
2. Otherwise, if the call has a **partner**, the module looks up that partner's most
   recent open customer invoice.
3. If one is found, it is attached to the call's `invoice` field.

An invoice qualifies only when **all** of these hold:

| Condition | Value |
|-----------|-------|
| Move type | `out_invoice` (customer invoice) |
| State | `posted` |
| Payment state | not `paid` |

The most recent qualifying invoice wins (ordered by invoice date, then id).

!!! warning "Customer invoices only"
    The `move_type = out_invoice` filter is deliberate: it prevents vendor bills,
    credit notes, and other move types from being attached to a customer call. Do
    not relax this filter.

### Fields added to the invoice

The module adds `connect_calls` (all linked calls) and the `connect_calls_count`
shown on the **Calls** smart button, plus read-only `partner_phone` /
`partner_mobile` fields (related to the partner). The invoice search view gains
these two as searchable fields.

## Working with a linked call

On the **Connect call form**, the **Invoice** notebook page shows the linked invoice
and an **Unlink** button (visible only when an invoice is set). The call list gains
an optional `Invoice` column (right of `Partner`).

On the **invoice form**, a **Calls** smart button (phone icon) opens all calls
linked to that invoice.

## Call summaries

If the core OpenAI transcription/summarization feature is enabled and the shared
**Register Summary** setting (`connect.settings.register_summary`) is on, then when a
call gains a summary and is linked to an invoice, that summary is posted to the
invoice's chatter automatically.

!!! info "Register Summary is a core setting"
    `register_summary` lives on the shared `connect.settings` record and governs
    summary posting for **all** Connect bridges, not just Accounting. Configure it
    under the Connect core settings.

## License gate

Automatic invoice matching and summary posting check the Oduist Connect Account
license (`check_license('connect_account')`) silently — if it is not active, calls
are still recorded but no invoice is linked and no summary is posted.
