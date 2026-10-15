# Configuration

All configuration for this module lives on the shared `connect.settings`
singleton, exposed as a **Helpdesk** page on the Connect settings form. Open it
via **Connect ▸ Configuration ▸ Settings ▸ Helpdesk** (Connect Administrator
only).

## Auto-create rules

When a call ends, the module can create a helpdesk ticket for it. Auto-creation
runs in `register_call()` — i.e. **after the call fully ends** — so the
answered/missed classification is reliable. The rules are evaluated per
direction; a call that already has a ticket is skipped.

### Incoming calls

| Field | Default | Effect |
|-------|---------|--------|
| **Auto Create Tickets** (`auto_create_tickets_for_in_calls`) | Off | Master toggle for incoming calls. When off, no incoming call ever auto-creates a ticket. |
| **For Answered Calls** (`auto_create_tickets_for_in_answered_calls`) | On | Create a ticket when the incoming call was answered (`status == 'completed'`). |
| **For Not Answered Calls** (`auto_create_tickets_for_in_missed_calls`) | On | Create a ticket when the incoming call was missed. |
| **For Unknown Callers** (`auto_create_tickets_for_in_unknown_callers`) | Off | Create a ticket when the caller does not match a contact (`partner` is empty). |

### Outgoing calls

| Field | Default | Effect |
|-------|---------|--------|
| **Auto Create Tickets** (`auto_create_tickets_for_out_calls`) | Off | Master toggle for outgoing calls. |
| **For Answered Calls** (`auto_create_tickets_for_out_answered_calls`) | On | Create a ticket when the outgoing call was answered. |
| **For Not Answered Calls** (`auto_create_tickets_for_out_missed_calls`) | On | Create a ticket when the outgoing call was not connected. |

!!! note "Internal calls are ignored"
    Outgoing calls to local PBX users (`called_pbx_users` is set) never
    auto-create a ticket, so internal calls between colleagues do not generate
    tickets.

### Auto-create options

Shown only when either master toggle is on:

| Field | Description |
|-------|-------------|
| **Default Helpdesk Team** (`auto_create_tickets_team`) | Team (`helpdesk.team`) assigned to auto-created tickets. |
| **Default Assignee** (`auto_create_tickets_user`) | Fallback assignee (`res.users`, internal users only) used when no PBX user maps to the call. |

The assignee is resolved in this order: for incoming calls, the PBX user who
answered, otherwise the first called PBX user, otherwise the **Default
Assignee**; for outgoing calls, the calling user, otherwise the **Default
Assignee**. The new ticket's name is the partner name, falling back to the
external number, and the number is stored in `partner_phone` when the caller is
unknown.

!!! info "How the sub-toggles combine"
    The three incoming sub-rules (answered / missed / unknown) are evaluated in
    order and are effectively OR-ed: the ticket is created if **any** enabled
    rule matches the call. Leaving all sub-toggles off while the master toggle
    is on means no ticket is ever created for that direction.

## Phone matching (linking existing tickets)

Independently of auto-creation, when a call starts the module tries to attach an
**existing open ticket** to it (`process_call_event()`):

- For incoming calls it looks up the **caller** number, for outgoing calls the
  **called** number.
- Matching is by `phone_normalized` (`+` plus the stripped digits of the
  ticket's `partner_phone`), trying the `+<digits>` form first and then the raw
  digits.
- Only **active** tickets in a **non-folded** stage (or no stage) are
  considered. If several match, the most recent (highest id) is used and a
  warning is logged.

Numbers shorter than the minimum extension length are ignored, so internal
extensions are not matched to tickets.

## Call summaries to the ticket

If the core OpenAI summary feature is enabled and the core **Register Summary**
setting (`register_summary`) is on, then whenever a call's `summary` field is
written and the call has a linked ticket, the summary is posted to that
ticket's chatter. This is driven by a constraint on the `summary` field, so it
happens automatically when the transcription/summary job completes.

## Manual call/ticket actions

On the **Connect call** form (**Connect ▸ Calls**):

- **Ticket** button — creates or opens the ticket for this call. If the call has
  no ticket yet, it first tries to match an existing open ticket by number; if
  none is found it opens a new ticket form pre-filled with the call's partner
  and number, and links it to the call on save. Requires an active license.
- **Helpdesk** notebook page — shows the linked `ticket` and an **Unlink**
  button to detach it.
- The call list gains a **Ticket** column (shown by default).

On the **Helpdesk ticket** form the module adds a **Calls** stat button that
opens all `connect.call` records linked to the ticket, an optional **Calls**
column on the ticket list, and `partner_phone` as a search field.
