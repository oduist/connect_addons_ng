# 012 — Add connect_crm Module

## Problem

The old `connect_crm` module (from `odoo19/addons_connect`) needs to be ported to the
new modular architecture. A decision is needed on where CRM integration logic lives.

## Options Considered

**A. Absorb into core `connect`**
Merge CRM fields/logic directly into `connect.call` and `connect.settings`.
- Pro: fewer modules
- Con: violates the core boundary rule — core would import `crm`, making it non-optional

**B. Absorb into `connect_twilio` or `connect_freeswitch`**
Put CRM logic inside a provider module.
- Pro: no new module
- Con: CRM is provider-agnostic; binding it to one provider makes it unavailable to the other

**C. Separate `connect_crm` module (chosen)**
A new module depends on `connect` + `crm` + `utm`, independent of any provider.
- Pro: clean separation; works with Twilio, FreeSWITCH, or both; installable independently
- Con: one more module to maintain

## Decision

Option C. `connect_crm` is a separate module that depends only on `connect`, `crm`, and `utm`.
It does not import or depend on any provider module (`connect_twilio`, `connect_freeswitch`).

## Changes vs Old Module

- Removed "Twilio" from name/description (the old module was mislabeled)
- Removed Odoo < 17 compatibility branches (project targets 17–19 only)
- Removed legacy `_sql_constraints` in `utm.py` (use `Constraint` class, 19+ only)
- Security groups use `connect.group_webhook` (consistent with other modules)
- Import path for `ODUIST_MODULES` updated to match new package structure
