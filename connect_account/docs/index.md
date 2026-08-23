# Oduist Connect Account — Administrator Guide

`connect_account` is a **provider-agnostic bridge** that links calls in the Oduist
Connect telephony platform to Odoo customer invoices. When a call is recorded, the
module looks up an open (posted, unpaid) customer invoice for the call's partner and
attaches it to the `connect.call`.

Because the bridge depends only on the shared `connect.call` ledger — never on a
specific telephony provider — it works identically for calls handled through
Twilio, FreeSWITCH, Asterisk, Telnyx, Infobip, or any other Connect provider. All
providers funnel their events through the same `connect.call.process_call_event()`
hook, and this module extends that hook.

## What this module provides

| Area | Capability |
|------|------------|
| **Call linking** | Automatically attaches an open customer invoice to each call, matched by the call's **partner** |
| **Invoice form** | A **Calls** smart button on the invoice form lists all calls linked to that invoice; partner phone/mobile shown read-only |
| **Call form** | An **Invoice** notebook page shows the linked invoice, with an **Unlink** action |
| **Call list** | An optional `Invoice` column on the Connect call list |
| **Search** | Partner phone/mobile added as searchable fields on the invoice search view |
| **Summaries** | Optionally posts the OpenAI call summary to the linked invoice's chatter |

!!! info "Customer invoices only — lookup only, no create"
    Matching is scoped to **customer invoices** (`move_type = out_invoice`) that are
    **posted** and **not fully paid**. Vendor bills, credit notes, and other move
    types are never matched. Like a lookup, this bridge has **no create button** —
    invoices are never created from a call.

## Dependencies

From `__manifest__.py`:

- `connect` — the Oduist Connect core (shared call ledger).
- `account` — Odoo Invoicing / Accounting.

## Prerequisites

- The core `connect` module installed and configured with at least one telephony
  provider.
- Core partner matching working, so calls carry a `partner` for the lookup to use.
- A valid Oduist Connect Account license. Every hook checks the license silently;
  without it, calls are still recorded but no invoice is linked.

## Guide contents

1. [Configuration & Usage](configuration.md) — how invoice matching works, summary
   posting, and the license gate.
2. [Security](security.md) — access groups and the webhook grant.

!!! note "Menus"
    This bridge adds **no menu of its own**. Linked calls surface on the existing
    **Connect** call views and through the **Calls** smart button on each invoice.
    Configuration lives on the shared Connect settings.
