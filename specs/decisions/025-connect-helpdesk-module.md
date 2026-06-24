# 025 — Add connect_helpdesk Module

## Problem

The legacy `connect_helpdesk` module (in `odoo19/addons_connect`) links telephony
calls with Odoo Helpdesk tickets. It needs to be ported to the new modular
architecture in the same way `connect_crm` was (ADR 012).

## Options Considered

**A. Absorb into core `connect`**
Put ticket fields/logic in `connect.call` directly.
- Pro: fewer modules.
- Con: violates the core boundary rule — `connect` would then depend on
  `helpdesk`, which is Enterprise-only and not relevant to most installs.

**B. Absorb into a provider module (`connect_twilio` / `connect_freeswitch`)**
- Pro: no new module.
- Con: Helpdesk integration is provider-agnostic; binding it to one provider
  prevents the other from using it.

**C. Separate `connect_helpdesk` module (chosen)**
A new module depending only on `connect` + `helpdesk`, independent of any
provider. Mirrors the `connect_crm` port exactly.
- Pro: clean separation; works with Twilio, FreeSWITCH, or both.
- Con: one more module to maintain.

## Decision

Option C. `connect_helpdesk` lives alongside `connect_crm`, depends only on
`connect` + `helpdesk`, and registers itself in `ODUIST_MODULES` for license
tracking.

## Changes vs Legacy Module

- **Manifest:** version bumped to `19.0.1.0.0`; dropped Odoo 15/16 compat
  branches; simplified `post_init_hook(env)`.
- **Hook surface:** `on_call_status` removed; ticket auto-link moved to
  `process_call_event` (phone → ticket match at call start) and
  `register_call` (auto-create ticket at call end). Mirrors the CRM port.
- **Auto-create tickets (new):** the legacy code only had a `TODO` for this.
  The port adds it, configurable per direction/status/unknown-caller via
  `connect.settings`, with a default helpdesk team and assignee.
- **Security:** adds `security/webhook.xml` granting `connect.group_webhook`
  access to `helpdesk.ticket` (rwc), `helpdesk.stage` and `helpdesk.team` (r),
  plus a matching `ir.rule`. Legacy module had no webhook security.
- **Constraints:** no `_sql_constraints` were needed; any new ones would use
  `Constraint` from `odoo.models` (19+ only).
- **Ref field:** adds `ref = Reference(selection_add=[('helpdesk.ticket', ...)])`
  with `_get_ref` override, for parity with `connect_crm` and cross-record
  navigation.
- **View IDs:** renamed to NG convention (`view_*_connect_helpdesk`).
- **Inherit IDs:** call views inherit `connect.view_connect_call_{tree,form}`
  (new core IDs), not the legacy `connect.connect_call_{list,form,search}`.
- **Deferred:** the active-calls popup patch (`static/src/services/active_calls/`)
  is not ported yet — the core popup widget has not been moved into NG yet
  (same deferral as `connect_crm`).

## Consequences

- Helpdesk integration is now optional and cleanly separated.
- Auto-create behaviour is explicit and configurable — no silent ticket
  creation unless enabled.
- When the active-calls popup lands in NG core, a follow-up PR will add the
  ticket column patch.
