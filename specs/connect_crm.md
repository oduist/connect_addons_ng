# Connect CRM Module Specification

## Module Info

- **Name:** Oduist Connect CRM
- **Technical:** `connect_crm`
- **Version:** 19.0.1.0.0
- **Depends:** `connect`, `crm`, `utm`
- **Application:** False
- **License:** Other proprietary

## Overview

The `connect_crm` module bridges the telephony core (`connect`) with Odoo CRM.
It is **provider-agnostic** — it depends only on `connect.call` and `connect.settings`,
not on `connect_twilio` or `connect_freeswitch`. It can be installed alongside either
or both provider modules.

Responsibilities:
- Link `connect.call` records to `crm.lead` opportunities
- Auto-create leads on incoming/outgoing calls based on configurable rules
- Attribute calls to UTM sources via `utm.source.phone`
- Show lead info in the active calls popup widget
- Register call summaries (OpenAI transcriptions) to linked leads

---

## Models (connect_crm/models/) — all use `_inherit` unless noted

### 1. settings.py — `_inherit = 'connect.settings'`

Registers `'connect_crm'` in `ODUIST_MODULES` for license tracking.

**Additional Fields:**

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `auto_create_leads_for_in_calls` | Boolean | False | Master toggle: incoming calls |
| `auto_create_leads_for_in_answered_calls` | Boolean | True | Auto-create on answered incoming |
| `auto_create_leads_for_in_missed_calls` | Boolean | True | Auto-create on missed incoming |
| `auto_create_leads_for_in_unknown_callers` | Boolean | False | Auto-create for unknown callers |
| `auto_create_leads_for_out_calls` | Boolean | False | Master toggle: outgoing calls |
| `auto_create_leads_for_out_answered_calls` | Boolean | True | Auto-create on answered outgoing |
| `auto_create_leads_for_out_missed_calls` | Boolean | True | Auto-create on missed outgoing |
| `auto_create_leads_sales_person` | Many2one → `res.users` | — | Fallback sales person for auto-created leads |
| `auto_create_leads_type` | Selection: `lead`/`opportunity` | `'lead'` | Lead type for auto-created records |

---

### 2. call.py — `_inherit = 'connect.call'`

Links calls to CRM leads and UTM sources.

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `lead` | Many2one → `crm.lead` | ondelete='set null', tracked |
| `source` | Many2one → `utm.source` | ondelete='set null', tracked |
| `ref` | Reference (selection_add) | Adds `crm.lead` as ref option |

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `process_call_event()` | Override: on channel event, match phone to `lead` / `source` and attach to the call record |
| `register_call()` | Override: after call fully ends, run `_auto_create_lead()` if configured |
| `_auto_create_lead()` | Private: implements auto-creation logic based on call direction, status, and config |
| `_get_ref()` | Override: returns `crm.lead,<id>` if lead is set |
| `create_lead_button()` | UI action: create/link a lead from the call form |
| `unlink_crm_lead()` | UI action: unlink the lead from this call |
| `get_widget_fields()` | Override: adds `'lead'` to widget field list |
| `register_crm_lead_call_summary()` | Constrains `summary`: if call has summary + lead + config, post summary to lead chatter |

**Semantic note on auto-create timing:**
The old module hooked `on_call_status()` which fired on every status change. The new
core calls `register_call()` once when all channels have ended. Auto-create therefore
runs at call completion, not during ringing. This is correct for answered/missed/unknown
scenarios (all require the call to be finished). Phone→lead *matching* (attaching an
existing lead to an active call) happens earlier in `process_call_event()` so the lead
appears in the active-calls widget while the call is still ringing.

---

### 3. crm_lead.py — `_inherit = 'crm.lead'`

Extends CRM leads with call tracking and phone-based matching.

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `connect_calls` | One2many → `connect.call` (field: `lead`) | All calls linked to this lead |
| `connect_calls_count` | Integer | Computed, stored; count of `connect_calls` |
| `phone_normalized` | Char | Computed, stored, indexed; normalized `phone` |
| `mobile_normalized` | Char | Computed, stored, indexed; normalized `mobile` |

**Additional Methods:**

| Method | Description |
|--------|-------------|
| `create_record_from_message()` | `@api.model`: create a lead from an inbound message if no existing lead matches the number |
| `_get_phone_normalized()` | Compute: normalize phone/mobile using partner phone normalization |
| `_get_connect_calls_count()` | Compute: count related calls |
| `get_lead_by_number()` | Search open leads by phone/mobile (strips, +prefix, e164 formats) |
| `create()` | Override: set `source_id` from context `call_id` if provided |
| `write()` / `unlink()` | Override: clear registry cache after changes (Odoo 17+: `env.registry.clear_cache()`) |

---

### 4. utm.py — `_inherit = 'utm.source'`

Associates UTM sources with phone numbers for call attribution.

**Additional Fields:**

| Field | Type | Notes |
|-------|------|-------|
| `phone` | Char | Phone number for this source; UNIQUE constraint |

**Constraints:** `UNIQUE(phone)` — "This phone number is already used!" (uses `Constraint` class, Odoo 19+)

---

### 5. message_configuration.py — `_inherit = 'connect.message_configuration'`

Adds `crm.lead` as a routing destination for inbound messages.

**Changes:**
- `destination` field: `selection_add = [('crm.lead', 'CRM Lead')]`

---

## Views (connect_crm/views/)

File naming follows the core convention `*_views.xml`.

### crm_lead_views.xml
- **Action** `connect_calls_lead_action`: window action showing calls for active lead
- **Form extension** (`crm.crm_lead_view_form`): stat button showing `connect_calls_count` (fa-phone icon)
- **Search extension** (`crm.view_crm_case_leads_filter`): adds `phone` and `mobile` search fields

### call_views.xml
- **List extension** (`connect.view_connect_call_tree`): adds `lead` (optional=show), `source` (optional=hide) columns
- **Form extension** (`connect.view_connect_call_form`): adds "Lead" button and "CRM" tab (lead, source fields + Unlink button)
- **Search:** core has no standalone search view. A new `connect.view_connect_call_search` record must be added to core `connect` first (prerequisite), then this module extends it to add lead/source search + group-by filters. Until then, search-by-lead is not available.

### utm_views.xml
- **List extension** (`utm.utm_source_view_tree`): adds `phone` column
- **Form extension** (`utm.utm_source_view_form`): adds `phone` field

### settings_views.xml
- **Form extension** (`connect.connect_settings_form`): inserts "CRM" notebook page with incoming/outgoing auto-create toggles and options

---

## Security (connect_crm/security/)

### webhook.xml

Access rules for `connect.group_webhook`:

| Model | Read | Create | Write | Notes |
|-------|------|--------|-------|-------|
| `crm.lead` | ✓ | ✓ | ✓ | Webhook can create/update leads |
| `mail.alias_domain` | ✓ | — | — | Read-only |
| `crm.stage` | ✓ | — | — | Read-only |
| `crm.team` | ✓ | — | — | Read-only |

Record rule: `connect.group_webhook` can access all leads `[(1,'=',1)]`.

---

## Static Assets (connect_crm/static/src/)

**Deferred.** The old module patched a `ConnectActiveCallsPopup` OWL component at
`@connect/services/active_calls/active_calls_popup`. That component does not yet
exist in the new core `connect` module (`static/src/components/` contains only
`license_banner`). Adding the Lead column to the active-calls widget is blocked
until the widget itself is ported to core.

When it is ported, this module will add:
- `services/active_calls/active_calls_popup.js` — patches `ConnectActiveCallsPopup` with `_onClickLead(ev, lead)` to open the linked lead
- `services/active_calls/active_calls_popup.xml` — extends the QWeb template with a "Lead" column

---

## Integration Points with Core

| Core concept | How connect_crm uses it |
|---|---|
| `connect.call.process_call_event()` | Override — match phone to lead/source at call start |
| `connect.call.register_call()` | Override — run auto-create lead logic at call end |
| `connect.call.get_widget_fields()` | Override — exposes `lead` in active calls widget |
| `connect.call.register_summary_to_rec()` | Called from `register_crm_lead_call_summary()` to post summary to lead |
| `connect.settings.get_param()` | Read CRM auto-create config values |
| `connect.message_configuration` | Adds `crm.lead` as message routing destination |
| `connect.group_webhook` | Security group for webhook-triggered lead creation |
| `ODUIST_MODULES` / `check_license('connect_crm')` | License tracking registration |

## Prerequisites in Core `connect`

Two changes to core `connect` are needed before (or as part of) this port:

1. **Add a standalone search view** `connect.view_connect_call_search` in `connect/views/call_views.xml` so integration modules can add provider- or domain-specific filters.
2. **Port the active-calls popup widget** from the old monolithic module to `connect/static/src/services/active_calls/` so `connect_crm` (and any other module) can extend it. This unblocks the deferred static assets above.

Both are tracked as TODOs and do not block the core data-model port of `connect_crm`.
