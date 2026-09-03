# Configuration & Usage

The HR bridge has **no settings of its own**. Once installed, it works
automatically. This page explains how the automatic linking behaves and the two
shared settings that influence it.

## How employees are matched

Matching runs inside `connect.call.process_call_event()` — the hook every provider
calls when a call is created — immediately after the core has recorded the call:

1. The module picks the **other party's** number: the **caller** for an incoming
   call, the **called** number for an outgoing call.
2. That number is normalized and looked up against the employee's normalized
   **Work Phone** (`work_phone`) and **Work Mobile** (`mobile_phone`).
3. If exactly one (most recent) employee matches, it is attached to the call's
   `employee` field.

!!! note "Short numbers are ignored"
    A number shorter than the internal-extension threshold is skipped, so internal
    extensions are never mistakenly matched against a full 10+ digit phone number.
    The lookup tries the `+<digits>` form first, then the bare digits.

The match runs only when the call has no employee yet, so a manual assignment is
never overwritten. Matches are recorded in the `connect.debug` log for
troubleshooting.

### Fields added to the employee

To support fast lookup, the module adds two stored, indexed helper fields computed
from the standard phone fields — `phone_normalized` (from Work Phone) and
`mobile_normalized` (from Work Mobile). It also adds `connect_calls` (all linked
calls) and the `connect_calls_count` shown on the **Calls** smart button. The
employee search view gains **Work Phone** and **Work Mobile** as searchable fields.

## Working with a linked call

On the **Connect call form**, the **Employee** notebook page shows the linked
employee and an **Unlink** button (visible only when an employee is set). The call
list gains an optional `Employee` column (right of `Partner`).

On the **employee form**, a **Calls** smart button (phone icon) opens all calls
linked to that employee.

## Call summaries

If the core OpenAI transcription/summarization feature is enabled and the shared
**Register Summary** setting (`connect.settings.register_summary`) is on, then when a
call gains a summary and is linked to an employee, that summary is posted to the
employee's chatter automatically.

!!! info "Register Summary is a core setting"
    `register_summary` lives on the shared `connect.settings` record and governs
    summary posting for **all** Connect bridges, not just HR. Configure it under the
    Connect core settings.

## License gate

Every automatic action — number matching and summary posting — first checks the
Oduist Connect HR license (`check_license('connect_hr')`). If the license is not
active, calls are still recorded normally but no employee is linked and no summary
is posted. The check is silent, so a missing license never raises an error during
call ingestion.
