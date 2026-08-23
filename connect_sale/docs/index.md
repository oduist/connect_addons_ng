# Oduist Connect Sale — Administrator Guide

`connect_sale` is a **provider-agnostic bridge** that links calls in the Oduist
Connect telephony platform to Odoo sale orders. When a call is recorded, the module
looks up an open quotation or order for the call's partner and attaches it to the
`connect.call`. From a call you can also open — or create — a sale order in one
click.

Because the bridge depends only on the shared `connect.call` ledger — never on a
specific telephony provider — it works identically for calls handled through
Twilio, FreeSWITCH, Asterisk, Telnyx, Infobip, or any other Connect provider. All
providers funnel their events through the same `connect.call.process_call_event()`
hook, and this module extends that hook.

## What this module provides

| Area | Capability |
|------|------------|
| **Call linking** | Automatically attaches an open sale order to each call, matched by the call's **partner** |
| **Create from call** | A **Sale Order** stat button on the call form opens the linked order, or a new order pre-filled for the caller |
| **Order form** | A **Calls** smart button on the sale order form lists all calls linked to that order; partner phone/mobile shown read-only |
| **Call form** | A **Sale Order** notebook page shows the linked order, with an **Unlink** action |
| **Call list** | An optional `Sale Order` column on the Connect call list |
| **Search** | Partner phone/mobile added as searchable fields on the quotation and sales order search views |
| **Summaries** | Optionally posts the OpenAI call summary to the linked order's chatter |

!!! info "Matches by partner, not by number"
    Unlike the HR bridge, this module matches on the call's **partner**. The call
    must already have a partner (populated by the core's own partner matching)
    before the sale lookup runs.

## Dependencies

From `__manifest__.py`:

- `connect` — the Oduist Connect core (shared call ledger).
- `sale` — Odoo Sales.

## Prerequisites

- The core `connect` module installed and configured with at least one telephony
  provider.
- Core partner matching working, so calls carry a `partner` for the lookup to use.
- A valid Oduist Connect Sale license. The automatic matching checks the license
  silently; the **Sale Order** button raises an error if the license is not active.

## Guide contents

1. [Configuration & Usage](configuration.md) — how order matching works, the create
   button, summary posting, and the license gate.
2. [Security](security.md) — access groups and the webhook grant.

!!! note "Menus"
    This bridge adds **no menu of its own**. Linked calls surface on the existing
    **Connect** call views and through the **Calls** smart button on each sale
    order. Configuration lives on the shared Connect settings.
