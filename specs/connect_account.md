# Connect Account Module Specification

## Module Info

- **Name:** Oduist Connect Account
- **Technical:** `connect_account`
- **Version:** 19.0.1.0.1
- **Depends:** `connect`, `account`
- **Application:** False
- **License:** Other proprietary
- **Post-init hook:** `post_init_hook` — stamps the module install date and refreshes the Oduist license status

## Overview

The `connect_account` module bridges the telephony core (`connect`) with Odoo
Accounting/Invoicing. It is **provider-agnostic** — it depends only on
`connect.call`, not on `connect_twilio`, `connect_freeswitch`, `connect_asterisk`,
`connect_telnyx` or `connect_infobip`. It works for calls originated or received
through any of them, since all providers funnel events through the shared
`connect.call` ledger and its `process_call_event()` hook.

Responsibilities:
- Link `connect.call` records to `account.move` (invoice) by matching the call's
  partner against that partner's open (posted, unpaid) **customer** invoices
- Show the linked invoice in the call form/list and the active-calls widget
- Register call summaries (OpenAI transcriptions) to the linked invoice's chatter

Like `connect_sale`, this bridge matches **by partner**, not by phone number. Unlike
`connect_sale`/`connect_project`, it has **no create button** — invoices are never
created from a call; the link is a pure lookup against existing, open invoices.

**Bug fix vs. the legacy source:** the lookup is scoped to
`move_type = 'out_invoice'` (customer invoices only). The legacy module this was
ported from matched any open `account.move` regardless of type, which meant vendor
bills (`in_invoice`), credit notes, and other move types could get attached to a
customer support call. `get_invoice_by_partner()` here explicitly filters on
`move_type = 'out_invoice'`, `state = 'posted'`, `payment_state != 'paid'` — this is
a deliberate correction, not an oversight.

---

## Models (connect_account/models/) — all use `_inherit` unless noted

### 1. settings.py — `_inherit = 'connect.settings'`

Registers `'connect_account'` in `ODUIST_MODULES` (`models/license.py`) for license
tracking. Adds no fields.

### 2. call.py — `_inherit = 'connect.call'`

Links calls to invoices.

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `invoice` | Many2one → `account.move` | `ondelete='set null'`, tracked |
| `ref` | Reference (selection_add) | Adds `account.move` as a `ref` option |

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `process_call_event()` | Override: if the call has a partner and no invoice yet, looks up an open customer invoice for that partner via `get_invoice_by_partner()` and links it |
| `_get_ref()` | Override: returns `account.move,<id>` if `invoice` is set, else falls through to `super()` |
| `unlink_invoice()` | UI action: clear `invoice` on this call |
| `get_widget_fields()` | Override: adds `'invoice'` to the active-calls widget field list |
| `register_account_move_call_summary()` | `@api.constrains('summary')`: if the call has a summary, a linked invoice, and `register_summary` is enabled in settings, post the summary to the invoice's chatter |

**`process_call_event()` behavior:**

```python
if not call.invoice and call.partner:
    invoice = self.env['account.move'].get_invoice_by_partner(call.partner)
    if invoice:
        call.invoice = invoice
```

The lookup is gated by `check_license('connect_account', silent=True)` and wrapped
in a broad `try/except` so a lookup failure never breaks call ingestion. There is no
`create_invoice_button` — the "Invoice" notebook page on the call form only ever
shows an `field name="invoice"` picker plus an Unlink button, no create-from-call
action.

---

### 3. account_move.py — `_inherit = 'account.move'`

Extends invoices with call tracking, partner lookup, and phone display.

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `connect_calls` | One2many → `connect.call` (field: `invoice`) | All calls linked to this invoice |
| `connect_calls_count` | Integer | Computed, **stored** (`@api.depends('connect_calls')`); count of `connect_calls` |
| `partner_phone` | Char | `related='partner_id.phone'` — read-only display convenience on the invoice form/search |
| `partner_mobile` | Char | `related='partner_id.mobile'` — same |

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `_get_connect_calls_count()` | Compute (`@api.depends('connect_calls')`): `search_count` on `connect.call` filtered by `invoice` |
| `get_invoice_by_partner(partner)` | `@api.model` lookup: returns the most recent (`order='invoice_date desc, id desc'`, `limit=1`) invoice for `partner` where `state = 'posted'`, `move_type = 'out_invoice'`, and `payment_state != 'paid'`; runs `.sudo()` |

`get_invoice_by_partner` returns an empty recordset (not `False`) on no match,
consistent with the ORM convention used across the other bridges' lookup helpers.
The `move_type` filter is the bug-fix noted in the Overview above — do not relax it
back to "any move" when touching this method.

---

## Security (connect_account/security/webhook.xml)

| Model | Read | Create | Write | Unlink |
|-------|------|--------|-------|--------|
| `account.move` | ✓ | — | — | — |

**Why read-only suffices:** `process_call_event()` only sets `call.invoice` — a
field on `connect.call`, already writable by the webhook user through core security
— it never creates or writes `account.move` directly. `get_invoice_by_partner()`
and `register_summary_to_rec()` both run with elevated rights (`.sudo()` /
`with_user(SUPERUSER_ID)`), bypassing ACLs entirely. There is no create button —
invoices are never created from a call — and `unlink_invoice()` runs as the
interactive Connect user (their own rights), not the webhook user. The webhook
identity therefore never needs to create, write, or unlink `account.move` directly —
read access is the full requirement.

---

## Views (connect_account/views/)

### call_views.xml
- **List extension** (`connect.view_connect_call_tree`): adds `invoice`
  (`optional="show"`) after `partner`
- **Form extension** (`connect.view_connect_call_form`): adds an "Invoice" notebook
  page (`invoice` field + `unlink_invoice` button, `invisible="not invoice"`). No
  stat button is added to the call form — there is no create-from-call action to
  expose.

### account_move_views.xml
- **Action** `connect_calls_account_action`: window action listing calls
  (`domain="[('invoice', '=', active_id)]"`, `view_mode="list,form"`)
- **Form extension** (`account.view_move_form`): smart button in `button_box`
  showing `connect_calls_count` (fa-phone icon, `widget="statinfo"`), opening
  `connect_calls_account_action`; also inserts `partner_phone`/`partner_mobile`
  read-only fields with `widget="phone"` after `partner_id`
- **Search extension** (`account.view_account_invoice_filter`): adds
  `partner_phone`/`partner_mobile` as searchable fields after `partner_id`

---

## Integration Points with Core

| Core concept | How connect_account uses it |
|---|---|
| `connect.call.process_call_event()` | Override — match `call.partner` to an open customer invoice at call start |
| `connect.call.get_widget_fields()` | Override — exposes `invoice` in the active-calls widget |
| `connect.call.register_summary_to_rec()` | Called from `register_account_move_call_summary()` to post the summary to the invoice |
| `connect.settings.get_param('register_summary')` | Gate for posting call summaries |
| `connect.group_webhook` | Security group granted read-only access to `account.move` |
| `ODUIST_MODULES` / `check_license('connect_account')` | License tracking registration; every hook checks the license (`silent=True`) before acting |

---

## Prerequisites in Core `connect`

None — this bridge only relies on the standing `connect.call.process_call_event()`
hook, `get_widget_fields()`, `register_summary_to_rec()`, `connect.call.partner`
(already populated by core's own partner-matching) and `connect.settings`, all
already present in core.
