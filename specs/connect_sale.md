# Connect Sale Module Specification

## Module Info

- **Name:** Oduist Connect Sale
- **Technical:** `connect_sale`
- **Version:** 19.0.1.0.0
- **Depends:** `connect`, `sale`
- **Application:** False
- **License:** Other proprietary

## Overview

The `connect_sale` module bridges the telephony core (`connect`) with Odoo Sales.
It is **provider-agnostic** — it depends only on `connect.call`, not on
`connect_twilio`, `connect_freeswitch`, `connect_asterisk`, `connect_telnyx` or
`connect_infobip`. It works for calls originated or received through any of them,
since all providers funnel events through the shared `connect.call` ledger and its
`process_call_event()` hook.

Responsibilities:
- Link `connect.call` records to `sale.order` by matching the call's partner
  against that partner's open quotations/orders
- Create a new sale order (or open the already-linked one) directly from a call,
  via `create_sale_order_button`
- Show the linked order in the call form/list and the active-calls widget
- Register call summaries (OpenAI transcriptions) to the linked order's chatter

Unlike `connect_hr`, this bridge matches **by partner**, not by phone number — the
call must already have `partner` populated (set by core's own partner-matching in
`process_call_event()`) before the sale lookup runs.

---

## Models (connect_sale/models/) — all use `_inherit` unless noted

### 1. settings.py — `_inherit = 'connect.settings'`

Registers `'connect_sale'` in `ODUIST_MODULES` (`models/license.py`) for license
tracking. Adds no fields.

### 2. call.py — `_inherit = 'connect.call'`

Links calls to sale orders.

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `sale_order` | Many2one → `sale.order` | `ondelete='set null'`, tracked |
| `ref` | Reference (selection_add) | Adds `sale.order` as a `ref` option |

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `process_call_event()` | Override: if the call has a partner and no order yet, looks up an open order for that partner via `get_order_by_partner()` and links it |
| `_get_ref()` | Override: returns `sale.order,<id>` if `sale_order` is set, else falls through to `super()` |
| `create_sale_order_button()` | UI action: if not already linked, links (or creates via the target form) a sale order for the call's partner; opens the order form (existing or blank `New Sale Order` with `default_partner_id`/`connect_call_id` in context) |
| `unlink_sale_order()` | UI action: clear `sale_order` on this call |
| `get_widget_fields()` | Override: adds `'sale_order'` to the active-calls widget field list |
| `register_sale_order_call_summary()` | `@api.constrains('summary')`: if the call has a summary, a linked order, and `register_summary` is enabled in settings, post the summary to the order's chatter |

**`process_call_event()` behavior:**

```python
if not call.sale_order and call.partner:
    order = self.env['sale.order'].get_order_by_partner(call.partner)
    if order:
        call.sale_order = order
```

The lookup is gated by `check_license('connect_sale', silent=True)` and wrapped in
a broad `try/except` so a lookup failure never breaks call ingestion.

**`create_sale_order_button()` behavior:** re-runs the same partner lookup as a
fallback (in case the call was answered before a matching order existed and one was
created meanwhile), then opens the sale order form. `default_partner_id` and
`connect_call_id` travel in the action context; `sale.order.create()` reads
`connect_call_id` from context to back-link the new order onto the call (see below)
— this is how a brand-new order created through the button ends up linked, not a
direct field write from the button itself. The button raises `ValidationError` if
the `connect_sale` license is not active (unlike the silent, best-effort matching in
`process_call_event()`, since this is a direct user action).

---

### 3. sale_order.py — `_inherit = 'sale.order'`

Extends sale orders with call tracking, partner lookup, and phone display.

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `connect_calls` | One2many → `connect.call` (field: `sale_order`) | All calls linked to this order |
| `connect_calls_count` | Integer | Computed, **stored** (`@api.depends('connect_calls')`); count of `connect_calls` |
| `partner_phone` | Char | `related='partner_id.phone'` — read-only display convenience on the order form/search |
| `partner_mobile` | Char | `related='partner_id.mobile'` — same |

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `_get_connect_calls_count()` | Compute (`@api.depends('connect_calls')`): `search_count` on `connect.call` filtered by `sale_order` |
| `get_order_by_partner(partner)` | `@api.model` lookup: returns the most recent (`order='id desc'`, `limit=1`) order for `partner` whose `state` is `draft`, `sent`, or `sale` (i.e. still open — excludes `cancel` and, notably, does not special-case `done`/locked orders beyond the explicit whitelist); runs `.sudo()` |
| `create()` | Override (`@api.model_create_multi`): if `connect_call_id` is present in context, back-links the first created order onto that call (`call.sale_order = recs[0]`); clears the registry cache (`self.env.registry.clear_cache()`) when records were created |

`get_order_by_partner` returns an empty recordset (not `False`) on no match,
consistent with the ORM convention used across the other bridges' lookup helpers.

---

## Security (connect_sale/security/webhook.xml)

| Model | Read | Create | Write | Unlink |
|-------|------|--------|-------|--------|
| `sale.order` | ✓ | — | — | — |

**Why read-only suffices:** `process_call_event()` only sets `call.sale_order` — a
field on `connect.call`, already writable by the webhook user through core security
— it never creates or writes `sale.order` directly. `get_order_by_partner()` and
`register_summary_to_rec()` both run with elevated rights (`.sudo()` /
`with_user(SUPERUSER_ID)`), bypassing ACLs entirely. `create_sale_order_button()`
and `unlink_sale_order()` run as the interactive Connect user (their own record
rights on `sale.order`, granted separately through Sales' own security groups), not
the webhook user. The webhook identity therefore never needs to create, write, or
unlink `sale.order` directly — read access is the full requirement.

---

## Views (connect_sale/views/)

### call_views.xml
- **List extension** (`connect.view_connect_call_tree`): adds `sale_order`
  (`optional="show"`) after `partner`
- **Form extension** (`connect.view_connect_call_form`): adds a "Sale Order" stat
  button (fa-shopping-cart icon) after `create_partner_button`, plus a "Sale Order"
  notebook page (`sale_order` field + `unlink_sale_order` button, `invisible="not
  sale_order"`)

### sale_order_views.xml
- **Action** `connect_calls_sale_action`: window action listing calls
  (`domain="[('sale_order', '=', active_id)]"`, `view_mode="list,form"`)
- **Form extension** (`sale.view_order_form`): smart button in `button_box` showing
  `connect_calls_count` (fa-phone icon, `widget="statinfo"`), opening
  `connect_calls_sale_action`; also inserts `partner_phone`/`partner_mobile`
  read-only fields after `partner_id`
- **Search extensions** (`sale.sale_order_view_search_inherit_quotation` and
  `sale.sale_order_view_search_inherit_sale`): add `partner_phone`/`partner_mobile`
  as searchable fields after `partner_id`, on both the quotations and the sales
  order search views

---

## Integration Points with Core

| Core concept | How connect_sale uses it |
|---|---|
| `connect.call.process_call_event()` | Override — match `call.partner` to an open `sale.order` at call start |
| `connect.call.get_widget_fields()` | Override — exposes `sale_order` in the active-calls widget |
| `connect.call.register_summary_to_rec()` | Called from `register_sale_order_call_summary()` to post the summary to the order |
| `connect.settings.get_param('register_summary')` | Gate for posting call summaries |
| `connect.debug` | Not used directly by this bridge (no number-matching to log) |
| `connect.group_webhook` | Security group granted read-only access to `sale.order` |
| `ODUIST_MODULES` / `check_license('connect_sale')` | License tracking registration; every hook checks the license (`silent=True` in matching, raising in the button) before acting |

---

## Prerequisites in Core `connect`

None — this bridge only relies on the standing `connect.call.process_call_event()`
hook, `get_widget_fields()`, `register_summary_to_rec()`, `connect.call.partner`
(already populated by core's own partner-matching) and `connect.settings`, all
already present in core.
