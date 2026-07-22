# Connect HR Module Specification

## Module Info

- **Name:** Oduist Connect HR
- **Technical:** `connect_hr`
- **Version:** 19.0.1.0.0
- **Depends:** `connect`, `hr`
- **Application:** False
- **License:** Other proprietary

## Overview

The `connect_hr` module bridges the telephony core (`connect`) with Odoo HR. It is
**provider-agnostic** — it depends only on `connect.call`, not on `connect_twilio`,
`connect_freeswitch`, `connect_asterisk`, `connect_telnyx` or `connect_infobip`.
It works for calls originated or received through any of them, since all providers
funnel events through the shared `connect.call.process_call_event()` hook.

Responsibilities:
- Link `connect.call` records to `hr.employee` by matching the caller/called number
  against the employee's work or mobile phone
- Show the linked employee in the call form/list and the active-calls widget
- Register call summaries (OpenAI transcriptions) to the linked employee's chatter

Unlike `connect_crm`/`connect_sale`/`connect_project`, this bridge has **no
auto-create and no create button**: employees are managed exclusively through HR
onboarding, never spawned from a phone call. The link is a pure lookup — the number
must already belong to an existing employee.

---

## Models (connect_hr/models/) — all use `_inherit` unless noted

### 1. settings.py — `_inherit = 'connect.settings'`

Registers `'connect_hr'` in `ODUIST_MODULES` (`models/license.py`) for license
tracking. Adds no fields — the module has no configurable behavior of its own.

### 2. call.py — `_inherit = 'connect.call'`

Links calls to HR employees.

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `employee` | Many2one → `hr.employee` | `ondelete='set null'`, tracked |
| `ref` | Reference (selection_add) | Adds `hr.employee` as a `ref` option |

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `process_call_event()` | Override: on channel event, look up the employee by caller/called number and attach it to the call if not already set |
| `_get_ref()` | Override: returns `hr.employee,<id>` if `employee` is set, else falls through to `super()` |
| `unlink_employee()` | UI action: clear `employee` on this call |
| `get_widget_fields()` | Override: adds `'employee'` to the active-calls widget field list |
| `register_hr_employee_call_summary()` | `@api.constrains('summary')`: if the call has a summary, a linked employee, and `register_summary` is enabled in settings, post the summary to the employee's chatter |

**`process_call_event()` behavior:**

```python
if not call.employee:
    number = call.caller if call.direction == 'incoming' else call.called
    employee = self.env['hr.employee'].get_employee_by_number(number)
    if employee:
        call.employee = employee
```

The number picked depends on call direction — the *other party's* number is always
what is matched (caller for inbound, called for outbound), mirroring the pattern
used by `connect_crm`'s lead matching. The lookup is gated by
`check_license('connect_hr', silent=True)` and wrapped in a broad
`try/except` so a lookup failure never breaks call ingestion.

There is no `create_employee_button` — the "Employee" notebook page on the call
form only ever shows a `field name="employee"` picker plus an Unlink button, no
create-from-call action.

---

### 3. hr_employee.py — `_inherit = 'hr.employee'`

Extends employees with call tracking and number-based lookup.

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `connect_calls` | One2many → `connect.call` (field: `employee`) | All calls linked to this employee |
| `connect_calls_count` | Integer | Computed, **stored** (`@api.depends('connect_calls')`); count of `connect_calls` |
| `phone_normalized` | Char | Computed, stored, indexed; normalized `work_phone` |
| `mobile_normalized` | Char | Computed, stored, indexed; normalized `mobile_phone` |

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `_get_connect_calls_count()` | Compute (`@api.depends('connect_calls')`): `search_count` on `connect.call` filtered by `employee` |
| `_get_phone_normalized()` | Compute (`@api.depends('work_phone', 'mobile_phone')`): normalizes both fields via `res.partner._normalize_phone()` |
| `_search_employee_by_number()` | Private: searches `phone_normalized`/`mobile_normalized` (OR), most recent match wins (`order='id desc'`), logs the match via `connect.debug` |
| `get_employee_by_number(number, country=None)` | Public lookup: strips the number via `strip_number()`, bails out (returns an empty recordset) if it is shorter than `MAX_EXTEN_LEN` (avoids matching short internal extensions against 10+ digit phone numbers), then tries the `+<digits>` form first and the bare-digits form second |

`get_employee_by_number` deliberately returns an empty recordset (not `False`) on
no match/too-short input, consistent with the ORM convention used across the other
bridges' lookup helpers.

---

## Security (connect_hr/security/webhook.xml)

| Model | Read | Create | Write | Unlink |
|-------|------|--------|-------|--------|
| `hr.employee` | ✓ | — | — | — |

**Why read-only suffices:** `process_call_event()` only sets `call.employee` — a
field on `connect.call`, already writable by the webhook user through core
security — it never creates or writes `hr.employee` records; the lookup itself runs
unrestricted (ORM search, not a write). `register_hr_employee_call_summary()` posts
to the chatter via `register_summary_to_rec()`, which runs with elevated rights
(mirrors the core pattern used by `connect_crm`). There is no create button and
`unlink_employee()` clears a field on `connect.call`, run as the interactive Connect
user with their own rights, not the webhook user. The webhook identity therefore
never needs to create, write, or unlink `hr.employee` directly — read access is the
full requirement, so no broader grant is added.

---

## Views (connect_hr/views/)

### call_views.xml
- **List extension** (`connect.view_connect_call_tree`): adds `employee`
  (`optional="show"`) after `partner`
- **Form extension** (`connect.view_connect_call_form`): adds an "Employee"
  notebook page (`employee` field + `unlink_employee` button, `invisible="not
  employee"`). No stat-button is added to the call form — there is no
  create-from-call action to expose.

### hr_employee_views.xml
- **Action** `connect_calls_hr_action`: window action listing calls
  (`domain="[('employee', '=', active_id)]"`, `view_mode="list,form"`)
- **Form extension** (`hr.view_employee_form`): smart button in `button_box`
  showing `connect_calls_count` (fa-phone icon, `widget="statinfo"`), opening
  `connect_calls_hr_action`
- **Search extension** (`hr.view_employee_filter`): adds `work_phone` and
  `mobile_phone` as searchable fields, after `name`

---

## Integration Points with Core

| Core concept | How connect_hr uses it |
|---|---|
| `connect.call.process_call_event()` | Override — match caller/called number to `hr.employee` at call start |
| `connect.call.get_widget_fields()` | Override — exposes `employee` in the active-calls widget |
| `connect.call.register_summary_to_rec()` | Called from `register_hr_employee_call_summary()` to post the summary to the employee |
| `connect.settings.get_param('register_summary')` | Gate for posting call summaries |
| `connect.debug` | Logs employee-by-number matches (`_search_employee_by_number`) |
| `connect.group_webhook` | Security group granted read-only access to `hr.employee` |
| `ODUIST_MODULES` / `check_license('connect_hr')` | License tracking registration; every hook checks the license (`silent=True`) before acting |

---

## Prerequisites in Core `connect`

None — this bridge only relies on the standing `connect.call.process_call_event()`
hook, `get_widget_fields()`, `register_summary_to_rec()` and `connect.settings`,
all already present in core.
