# Connect Project Module Specification

## Module Info

- **Name:** Oduist Connect Project
- **Technical:** `connect_project`
- **Version:** 19.0.1.0.0
- **Depends:** `connect`, `project`
- **Application:** False
- **License:** Other proprietary

## Overview

The `connect_project` module bridges the telephony core (`connect`) with Odoo
Project. It is **provider-agnostic** — it depends only on `connect.call`, not on
`connect_twilio`, `connect_freeswitch`, `connect_asterisk`, `connect_telnyx` or
`connect_infobip`. It works for calls originated or received through any of them,
since all providers funnel events through the shared `connect.call` ledger and its
`process_call_event()` hook.

Responsibilities:
- Link `connect.call` records to **two** possible targets: `project.task` (primary)
  or `project.project` (fallback), matching the call's partner
- Create a new task (or open the already-linked one) directly from a call, via
  `create_task_button`
- Show the linked task/project in the call form/list and the active-calls widget
- Register call summaries (OpenAI transcriptions) to the linked task or project
- Extend `connect.recording` so recordings inherit the call's `task`/`project`
  link, giving both models a "Recorded Calls" notebook page

This is the only one of the four bridges with **two** target models instead of one:
a call can link to a `project.task` *or* a `project.project`, never both — the two
M2O fields are mutually exclusive by construction (see `_get_ref()` below).

---

## Models (connect_project/models/) — all use `_inherit` unless noted

### 1. settings.py — `_inherit = 'connect.settings'`

Registers `'connect_project'` in `ODUIST_MODULES` (`models/license.py`) for license
tracking. Adds no fields.

### 2. call.py — `_inherit = 'connect.call'`

Links calls to tasks/projects.

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `task` | Many2one → `project.task` | `ondelete='set null'`, tracked |
| `project` | Many2one → `project.project` | `ondelete='set null'`, tracked |
| `ref` | Reference (selection_add) | Adds both `project.task` and `project.project` as `ref` options |

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `process_call_event()` | Override: if the call has a partner and neither `task` nor `project` is set yet, looks up an open task first, falling back to a project |
| `_get_ref()` | Override: returns `project.task,<id>` if `task` is set, else `project.project,<id>` if `project` is set, else falls through to `super()` |
| `create_task_button()` | UI action: opens the linked task's form, or a blank "New Task" form pre-filled with `default_partner_id` and a `default_name` derived from the caller |
| `unlink_task()` | UI action: clears **both** `task` and `project` on this call |
| `get_widget_fields()` | Override: adds `'task'` and `'project'` to the active-calls widget field list |
| `register_project_call_summary()` | `@api.constrains('summary')`: posts the summary to `task` if set, else to `project` (`target = rec.task or rec.project`), gated by `register_summary` |

**`process_call_event()` lookup order (by-partner, open task first):**

```python
if not call.task and not call.project and call.partner:
    task = self.env['project.task'].sudo().search(
        [('partner_id', '=', call.partner.id),
         ('stage_id.fold', '=', False)], order='id desc', limit=1)
    if task:
        call.task = task
    else:
        project = self.env['project.project'].sudo().search(
            [('partner_id', '=', call.partner.id)], order='id desc', limit=1)
        if project:
            call.project = project
```

An **open** task (`stage_id.fold = False` — the task's kanban stage is not marked
"folded", i.e. not a Done/Cancelled-style stage) for the partner wins over a
project match. If no open task exists, the most recent project owned by the partner
is linked instead. The lookup is gated by `check_license('connect_project',
silent=True)` and wrapped in a broad `try/except` so a lookup failure never breaks
call ingestion. Unlike `connect_hr`/`connect_sale`/`connect_account`, this lookup
runs inline in `call.py` rather than delegating to a model method on the target —
there is no `get_task_by_partner()` helper on `project.task`.

**`create_task_button()` behavior:** does not re-run the by-partner lookup (unlike
`connect_sale.create_sale_order_button()`); it always opens either the already-linked
task or a blank form. `default_partner_id` and `connect_call_id` travel in the
action context; `project.task.create()` reads `connect_call_id` from context to
back-link the new task onto the call (see below). The button raises
`ValidationError` if the `connect_project` license is not active.

---

### 3. task.py — `_inherit = 'project.task'`

Extends tasks with call tracking, recordings, and phone display.

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `connect_calls` | One2many → `connect.call` (field: `task`) | All calls linked to this task |
| `connect_calls_count` | Integer | Computed, **stored** (`@api.depends('connect_calls')`); count of `connect_calls` |
| `recorded_calls` | One2many → `connect.recording` (field: `task`) | Recordings whose call is linked to this task (see `recording.py` below) |
| `partner_phone` | Char | `related='partner_id.phone'` — read-only display convenience |
| `partner_mobile` | Char | `related='partner_id.mobile'` — same |

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `_get_connect_calls_count()` | Compute (`@api.depends('connect_calls')`): `search_count` on `connect.call` filtered by `task` |
| `create()` | Override (`@api.model_create_multi`): if `connect_call_id` is present in context, back-links the first created task onto that call (`call.task = recs[0]`); clears the registry cache (`self.env.registry.clear_cache()`) when records were created |

There is no `get_task_by_partner()` classmethod on this model — the by-partner
lookup lives entirely in `call.py`'s `process_call_event()` (see above).

---

### 4. project.py — `_inherit = 'project.project'`

Extends projects with call tracking, recordings, and phone display (fallback
target — see Overview).

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `connect_calls` | One2many → `connect.call` (field: `project`) | All calls linked to this project |
| `connect_calls_count` | Integer | Computed, **stored** (`@api.depends('connect_calls')`); count of `connect_calls` |
| `recorded_calls` | One2many → `connect.recording` (field: `project`) | Recordings whose call is linked to this project (see `recording.py` below) |
| `partner_phone` | Char | `related='partner_id.phone'` — read-only display convenience |
| `partner_mobile` | Char | `related='partner_id.mobile'` — same |

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `_get_connect_calls_count()` | Compute (`@api.depends('connect_calls')`): `search_count` on `connect.call` filtered by `project` |

`project.project` has no `create()` override with a `connect_call_id` back-link —
only tasks (the primary target) support create-from-call.

---

### 5. recording.py — `_inherit = 'connect.recording'`

Gives recordings the same task/project link as their parent call, so the
"Recorded Calls" page on a task/project form can list recordings directly (rather
than joining through `connect_calls` → recordings each time).

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `task` | Many2one → `project.task` | `ondelete='set null'`, `readonly=True` |
| `project` | Many2one → `project.project` | `ondelete='set null'`, `readonly=True` |

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `create()` | Override (`@api.model_create_multi`): after creation, copies `rec.call.task` → `rec.task` if the call has a task, else `rec.call.project` → `rec.project` if the call has a project |

This mirrors the call's own mutual-exclusivity: a recording gets `task` **or**
`project`, matching whichever the parent call resolved to, never both. Both fields
are `readonly=True` — they are derived at creation time from the call, not
independently editable.

---

## Security (connect_project/security/webhook.xml)

| Model | Read | Create | Write | Unlink |
|-------|------|--------|-------|--------|
| `project.task` | ✓ | — | — | — |
| `project.project` | ✓ | — | — | — |

**Why read-only suffices:** `process_call_event()` only sets `call.task`/
`call.project` — fields on `connect.call`, already writable by the webhook user
through core security — it only **links** existing task/project records, never
creates them; the lookup searches run `.sudo()`, bypassing ACLs. `create_task_button()`
runs as the interactive Connect user (their own rights on `project.task`, granted
separately through Project's own security groups), not the webhook user, and is the
only path that creates a `project.task`. The `connect.recording` create-hook
(task/project back-fill) writes `connect.recording` fields, not
`project.task`/`project.project` themselves. `register_summary_to_rec()` runs
`SUPERUSER`. The webhook identity therefore never needs to create, write, or unlink
`project.task`/`project.project` directly — read access is the full requirement for
both models.

---

## Views (connect_project/views/)

### call_views.xml
- **List extension** (`connect.view_connect_call_tree`): adds `task` and `project`
  (both `optional="show"`) after `partner`
- **Form extension** (`connect.view_connect_call_form`): adds a "Task" stat button
  (fa-tasks icon) after `create_partner_button`, plus a "Project" notebook page
  (`task` + `project` fields, and an `unlink_task` button visible whenever either
  is set: `invisible="not task and not project"`)

### task_views.xml
- **Action** `connect_calls_task_action`: window action listing calls
  (`domain="[('task', '=', active_id)]"`, `view_mode="list,form"`)
- **Form extension** (`project.view_task_form2`): smart button in `button_box`
  showing `connect_calls_count` (fa-phone icon, `widget="statinfo"`), opening
  `connect_calls_task_action`; inserts `partner_phone`/`partner_mobile` read-only
  fields with `widget="phone"` after `partner_id`; adds a "Recorded Calls"
  notebook page listing
  `recorded_calls` (`start_time`, `caller_number`, `called_number`,
  `recording_widget` rendered with `widget="html"`); caller/called numbers in
  the embedded list are plain fields

### project_views.xml
- **Action** `connect_calls_project_action`: window action listing calls
  (`domain="[('project', '=', active_id)]"`, `view_mode="list,form"`)
- **Form extension** (`project.edit_project`): same pattern as `task_views.xml` —
  smart button (`connect_calls_project_action`), `partner_phone`/`partner_mobile`
  fields with `widget="phone"`, and a "Recorded Calls" notebook page listing
  `recorded_calls` with caller/called numbers rendered as plain fields

---

## Integration Points with Core

| Core concept | How connect_project uses it |
|---|---|
| `connect.call.process_call_event()` | Override — match `call.partner` to an open task, else a project, at call start |
| `connect.call.get_widget_fields()` | Override — exposes `task`/`project` in the active-calls widget |
| `connect.call.register_summary_to_rec()` | Called from `register_project_call_summary()` to post the summary to the task or project |
| `connect.recording` | Extended with `task`/`project` back-fill on `create()`, powering the "Recorded Calls" pages |
| `connect.settings.get_param('register_summary')` | Gate for posting call summaries |
| `connect.group_webhook` | Security group granted read-only access to `project.task` and `project.project` |
| `ODUIST_MODULES` / `check_license('connect_project')` | License tracking registration; every hook checks the license (`silent=True` in matching, raising in the button) before acting |

---

## Prerequisites in Core `connect`

None — this bridge only relies on the standing `connect.call.process_call_event()`
hook, `get_widget_fields()`, `register_summary_to_rec()`, `connect.recording`,
`connect.call.partner` (already populated by core's own partner-matching) and
`connect.settings`, all already present in core.
