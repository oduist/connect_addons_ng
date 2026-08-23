# Configuration & Usage

The Sales bridge has **no settings of its own**. Once installed, it works
automatically. This page explains how the automatic linking behaves, the create
button, and the two shared settings that influence it.

## How sale orders are matched

Matching runs inside `connect.call.process_call_event()` — the hook every provider
calls when a call is created — right after the core has recorded the call and
resolved its partner:

1. If the call already has a linked order, nothing happens (a manual assignment is
   never overwritten).
2. Otherwise, if the call has a **partner**, the module looks up that partner's most
   recent **open** order.
3. If one is found, it is attached to the call's `sale_order` field.

An order counts as **open** when its state is **Quotation** (`draft`), **Quotation
Sent** (`sent`), or **Sales Order** (`sale`). Cancelled orders are excluded. The
most recent match wins.

### Fields added to the sale order

The module adds `connect_calls` (all linked calls) and the `connect_calls_count`
shown on the **Calls** smart button, plus read-only `partner_phone` /
`partner_mobile` fields (related to the partner). The quotation and sales order
search views gain these two as searchable fields.

## Working with a linked call

On the **Connect call form**:

- The **Sale Order** notebook page shows the linked order and an **Unlink** button
  (visible only when an order is set).
- A **Sale Order** stat button (cart icon) opens the linked order, or — if none is
  linked yet — first retries the partner lookup and then opens a new **New Sale
  Order** form pre-filled with the caller as customer. A brand-new order created
  this way is back-linked onto the call automatically (the call id travels in the
  form context and `sale.order.create()` reads it).

The call list gains an optional `Sale Order` column (right of `Partner`).

On the **sale order form**, a **Calls** smart button (phone icon) opens all calls
linked to that order.

!!! warning "License required for the button"
    The **Sale Order** button raises *"Connect Sale license is not activated!"* if
    the license is inactive, because it is a direct user action. The silent
    automatic matching, by contrast, simply skips linking when the license is
    missing.

## Call summaries

If the core OpenAI transcription/summarization feature is enabled and the shared
**Register Summary** setting (`connect.settings.register_summary`) is on, then when a
call gains a summary and is linked to an order, that summary is posted to the
order's chatter automatically.

!!! info "Register Summary is a core setting"
    `register_summary` lives on the shared `connect.settings` record and governs
    summary posting for **all** Connect bridges, not just Sales. Configure it under
    the Connect core settings.

## License gate

Automatic order matching and summary posting check the Oduist Connect Sale license
(`check_license('connect_sale')`) silently — if it is not active, calls are still
recorded but no order is linked and no summary is posted.
