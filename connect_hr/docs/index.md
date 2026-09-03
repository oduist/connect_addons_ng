# Oduist Connect HR — Administrator Guide

`connect_hr` is a **provider-agnostic bridge** that links calls in the Oduist
Connect telephony platform to Odoo HR employees. When a call arrives or is placed,
the module matches the other party's phone number against employee records and
attaches the matching `hr.employee` to the `connect.call`.

Because the bridge depends only on the shared `connect.call` ledger — never on a
specific telephony provider — it works identically for calls handled through
Twilio, FreeSWITCH, Asterisk, Telnyx, Infobip, or any other Connect provider. All
providers funnel their events through the same `connect.call.process_call_event()`
hook, and this module extends that hook.

## What this module provides

| Area | Capability |
|------|------------|
| **Call linking** | Automatically attaches the matching `hr.employee` to each call, matched by the caller/called number against the employee's work or mobile phone |
| **Employee form** | A **Calls** smart button on the employee form opens the list of calls linked to that employee |
| **Call form** | An **Employee** notebook page on the call form shows the linked employee, with an **Unlink** action |
| **Call list** | An optional `Employee` column on the Connect call list |
| **Summaries** | Optionally posts the OpenAI call summary to the linked employee's chatter |

!!! info "Lookup only — no create"
    Unlike the Sales and Project bridges, this module has **no create button**.
    Employees are managed through normal HR onboarding and are never spawned from a
    phone call. The link is a pure lookup: the number must already belong to an
    existing employee.

## Dependencies

From `__manifest__.py`:

- `connect` — the Oduist Connect core (shared call ledger).
- `hr` — Odoo Human Resources.

## Prerequisites

- The core `connect` module installed and configured with at least one telephony
  provider.
- Employees with their **Work Phone** and/or **Work Mobile** populated — matching
  is done against these two fields only.
- A valid Oduist Connect HR license. Every hook checks the license before acting;
  without it, calls are still recorded but no employee is linked.

## Guide contents

1. [Configuration & Usage](configuration.md) — how number matching works, summary
   posting, and the license gate.
2. [Security](security.md) — access groups and the webhook grant.

!!! note "Menus"
    This bridge adds **no menu of its own**. Linked calls surface on the existing
    **Connect** call views and through the **Calls** smart button on each employee
    form. Configuration lives on the shared Connect settings.
