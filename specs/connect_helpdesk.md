# Connect Helpdesk Module Specification

## Module Info

- **Name:** Oduist Connect Helpdesk
- **Technical:** `connect_helpdesk`
- **Version:** 18.0.1.0.0
- **Depends:** `connect`, `helpdesk`
- **Application:** False
- **License:** Other proprietary

## Overview

`connect_helpdesk` bridges the telephony core (`connect`) with Odoo Helpdesk
(Enterprise). It is **provider-agnostic** — it depends only on `connect.call`
and `connect.settings`, not on `connect_twilio` or `connect_freeswitch`. It
can run alongside either or both provider modules.

Responsibilities:
- Link `connect.call` records to `helpdesk.ticket`.
- Auto-create tickets on incoming/outgoing calls based on configurable rules.
- Register call summaries (OpenAI transcripts) to linked tickets.

Legacy module (`odoo19/addons_connect/connect_helpdesk`) had a `TODO` for
auto-create; this port implements it, mirroring the `connect_crm` pattern.

---

## Models (connect_helpdesk/models/) — all use `_inherit`

### 1. settings.py — `_inherit = 'connect.settings'`

Registers `'connect_helpdesk'` in `ODUIST_MODULES` for license tracking.

**Additional Fields:**

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `auto_create_tickets_for_in_calls` | Boolean | False | Master toggle: incoming calls |
| `auto_create_tickets_for_in_answered_calls` | Boolean | True | Auto-create on answered incoming |
| `auto_create_tickets_for_in_missed_calls` | Boolean | True | Auto-create on missed incoming |
| `auto_create_tickets_for_in_unknown_callers` | Boolean | False | Auto-create for unknown callers |
| `auto_create_tickets_for_out_calls` | Boolean | False | Master toggle: outgoing calls |
| `auto_create_tickets_for_out_answered_calls` | Boolean | True | Auto-create on answered outgoing |
| `auto_create_tickets_for_out_missed_calls` | Boolean | True | Auto-create on missed outgoing |
| `auto_create_tickets_team` | Many2one → `helpdesk.team` | — | Team for auto-created tickets |
| `auto_create_tickets_user` | Many2one → `res.users` | — | Fallback assignee (domain: `share=False`) |

---

### 2. call.py — `_inherit = 'connect.call'`

Links calls to helpdesk tickets.

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `ticket` | Many2one → `helpdesk.ticket` | ondelete=`set null`, tracked |
| `ref` | Reference (selection_add) | Adds `helpdesk.ticket` as ref option |

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `process_call_event()` | Override: on channel event, match phone → ticket and attach to the call record |
| `register_call()` | Override: after call fully ends, run `_auto_create_ticket()` if configured |
| `_auto_create_ticket()` | Private: implements auto-creation logic by direction/status/unknown-caller |
| `_get_ref()` | Override: returns `helpdesk.ticket,<id>` if ticket is set |
| `create_ticket_button()` | UI action: create/link a ticket from the call form |
| `unlink_ticket()` | UI action: unlink the ticket from this call |
| `get_widget_fields()` | Override: adds `'ticket'` to widget field list |
| `register_helpdesk_ticket_call_summary()` | Constrains `summary`: if call has summary + ticket + config, post summary to ticket chatter |

**Semantic note on auto-create timing:**
Phone→ticket *matching* (attaching an existing ticket to an active call) runs
in `process_call_event()` at call start. Auto-create of a new ticket runs in
`register_call()` when the call fully ends, so answered/missed/unknown
classification is reliable.

---

### 3. ticket.py — `_inherit = 'helpdesk.ticket'`

Adds phone-lookup and a back-reference to calls.

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `connect_calls` | One2many → `connect.call.ticket` | All calls linked to this ticket |
| `connect_calls_count` | Integer, stored computed | Count for stat button |
| `phone_normalized` | Char, stored indexed | `+` + `strip_number(partner_phone)`; used for lookup |

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `get_ticket_by_number(number, country=None)` | Public: find an open ticket by phone, tries `+<digits>` then raw digits |
| `_search_ticket_by_number(number)` | Private: scoped to active records in non-folded stages |
| `_get_connect_calls_count()` | Compute |
| `_get_phone_normalized()` | Compute |
| `create()` | Override: if `connect_call_id` in context, link the new ticket to that call; clear registry cache |

---

## Security — security/webhook.xml

Grants `connect.group_webhook` the ability to create/update tickets received
via provider webhooks:

| Model | Read | Create | Write | Unlink |
|-------|------|--------|-------|--------|
| `helpdesk.ticket` | yes | yes | yes | no |
| `helpdesk.stage` | yes | no | no | no |
| `helpdesk.team` | yes | no | no | no |

Plus an `ir.rule` on `helpdesk.ticket` with `domain_force=[(1,'=',1)]` so the
webhook user can see all tickets.

---

## Views

- `views/ticket_views.xml` — inherits helpdesk form (adds a `oe_stat_button`
  with call count), tree (adds `connect_calls_count` optional column),
  search (adds `partner_phone`). Also defines `connect_calls_ticket_action`.
- `views/call_views.xml` — inherits core `connect.view_connect_call_tree`
  (adds `ticket` column) and `connect.view_connect_call_form` (adds a
  "Ticket" button next to "Create Partner" plus a Helpdesk notebook page
  with `ticket` field and Unlink button).
- `views/settings_views.xml` — adds a **Helpdesk** page on the Connect
  settings form with the auto-create toggles, default team and default
  assignee.

---

## Deferred

- Active-calls popup patch (`static/src/services/active_calls/`) — the core
  popup widget is not yet ported into NG. When it lands, add a small patch
  showing the ticket column in the popup and a click action routing to the
  ticket form (matches the legacy behaviour and the `connect_crm` plan).

---

## Frontend

None in this first iteration.

---

## Tests

Placed in `connect_helpdesk/tests/` and run via oduflow:
`run_odoo_tests connect_helpdesk`.
