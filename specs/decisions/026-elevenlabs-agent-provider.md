# 026 — ElevenLabs agent: explicit `provider_id`

## Status
Accepted — 2026-05-29.

## Context

`connect.elevenlabs_agent` (in `connect_elevenlabs`) does not know which
telephony provider drives its calls. Provider behaviour leaks in through
two `auto_install=True` bridge modules that both `_inherit` the agent
model:

- `connect_elevenlabs_twilio` overrides `render()` and `transfer()`,
  adds Twilio-only fields (`twilio_sip_host`) and a Twilio default for
  `el_inbound_allowed_ips`. Tab "Twilio" is added unconditionally.
- `connect_elevenlabs_freeswitch` overrides `generate_dialplan()` and
  `transfer()`.

When **both** bridges are installed (the normal multi-provider setup
since ADR-023), several things misbehave:

1. There is no record-level signal saying "this agent is routed via
   Twilio" or "via FreeSWITCH". The Twilio tab and `twilio_sip_host`
   show up on every agent, including FS-only ones.
2. `transfer()` (`@api.model`) is resolved by Odoo's MRO — whichever
   bridge is loaded last wins for every agent, regardless of intent.
3. The Twilio override of `el_inbound_allowed_ips`'s `default=` is the
   last-loaded one; FS-only agents end up with Twilio signaling IPs as
   their default allow-list.
4. `connect.provider._for_record(agent)` returns an empty recordset
   because there is no `provider_id` on the agent. The agent is the only
   provider-scoped artefact in the codebase that opted out of the
   `provider_id` pattern used by `connect.exten`, `connect.call`,
   `connect.callflow`, `connect.number`, `connect.user.provider_ids`.

The fix is to make the agent's provider explicit, mirroring the rest
of the codebase, and then condition all provider-specific behaviour
(view tabs, field defaults, render/dialplan/transfer dispatch) on
`agent.provider_id.code`.

## Decision

Add `provider_id` (Many2one to `connect.provider`, required) to
`connect.elevenlabs_agent` in the **core** EL module. Bridge modules
keep their `_inherit` extensions but guard every provider-specific
override (`render`, `generate_dialplan`, `transfer`, default values) by
the agent's `provider_id.code`.

### 1. Data model — `connect_elevenlabs/models/agent.py`

```python
provider_id = fields.Many2one(
    'connect.provider',
    string='Provider',
    required=True,
    ondelete='restrict',
    default=lambda self: self._default_provider_id(),
    domain=lambda self: self._provider_domain(),
    help='Telephony provider that delivers calls to this ElevenLabs '
         'agent (SIP bridge + transfer back-channel).',
)
provider_code = fields.Char(
    related='provider_id.code', store=False, readonly=True,
    string='Provider code',
)
```

- `provider_id` is **required**. Existing dev installs with NULL rows
  upgrade by either dropping the DB or filling `provider_id` via shell
  before reinstall — explicitly: no migration script ships with this
  change.
- `_default_provider_id()` resolution order:
  1. If exactly one EL bridge module is installed → its provider.
  2. If both Twilio and FreeSWITCH bridges are installed → Twilio
     (matches the pre-change "last-loaded bridge wins" behaviour, which
     in practice was Twilio for historical reasons).
  3. If no EL bridge is installed → `False`, and `required=True` blocks
     creation. An agent with no bridge cannot route calls anyway.
- `_provider_domain()` restricts the dropdown to providers backed by an
  installed EL-bridge module. The mapping (provider code → bridge
  module name) is owned by each bridge: a bridge declares its code via
  a small registry hook (mechanism deferred to the implementation
  plan; either `ir.config_parameter` whitelist updated in
  `post_init_hook`, or a lookup against `ir.module.module` state).
- `provider_code` is a stored=False related used solely as a stable key
  for `invisible=` guards in view inheritance; using
  `provider_id.code` directly in `invisible=` is supported on 18.0/19.0
  but the related field gives more predictable on-change behaviour.

### 2. Pinned after provisioning

`provider_id` is editable on a fresh record. After
`_ensure_el_virtual_number()` has run (i.e. `el_virtual_number_uid` is
set), `write({'provider_id': ...})` raises `ValidationError` —
"Remove the extension to change provider". Rationale: the EL
`phone_number` entity is provisioned with a specific allow-list and
SIP route; swapping providers without first removing the extension
would leave a dangling EL-side entity routed against the wrong
inbound IP set. Auto-reprovisioning is rejected as too implicit for a
production-affecting change.

UI mirrors this: the selector is `readonly="exten or
el_virtual_number_uid"` in the form view.

### 3. UX — `connect_elevenlabs/views/agent.xml` + bridge views

- **Form, `oe_title`:** `<field name="provider_id" widget="radio"
  options="{'horizontal': true}"/>` next to `name`, with the readonly
  rule above. `<field name="provider_code" invisible="1"/>` follows so
  bridge views can reference it.
- **List view:** add `<field name="provider_id" optional="show"/>`
  after `name`.
- **`connect_elevenlabs_twilio/views/agent.xml`:** wrap the existing
  `<page name="twilio">` with `invisible="provider_code != 'twilio'"`.
- **`connect_elevenlabs_freeswitch`:** no view changes today (FS has
  no bridge-side agent fields). If FS-specific fields appear later, a
  symmetric `invisible="provider_code != 'freeswitch'"` page is added.
- **SIP Routing tab** (`el_inbound_allowed_ips`,
  `el_virtual_number_uid`) stays unconditional — both providers use
  the same EL-side artefacts.

### 4. Per-provider field defaults

Today, `connect_elevenlabs_twilio` redefines `el_inbound_allowed_ips`
on the agent model just to change its `default=`. With two bridges
loaded, the last one wins regardless of the agent's intended
provider. Replace this with a provider-dispatched default:

- On `connect.elevenlabs_agent`,
  `_default_el_inbound_allowed_ips(self)` reads `self._context` for
  the resolving provider (or falls back to `_default_provider_id()`)
  and delegates to `provider._elevenlabs_default_inbound_ips()`.
- Each EL bridge overrides `connect.provider` with a guarded
  `_elevenlabs_default_inbound_ips(self)`:
  - Twilio: returns `"\n".join(TWILIO_SIP_SIGNALING_IPS)`.
  - FreeSWITCH: returns `''` (allow-all by default; operators are
    expected to lock this down in production).
  - Base: returns `''`.
- The Twilio-side field redefinition is removed.

### 5. Dispatch — `render` / `generate_dialplan` / `transfer`

Each bridge guards its override by `self.provider_id.code` and calls
`super()` otherwise. This gives a clean dispatch chain identical in
spirit to the one on `connect.provider._originate_call` /
`_verify_webhook`.

```python
# connect_elevenlabs_twilio/models/agent.py
def render(self, request, params=None):
    self.ensure_one()
    if self.provider_id.code != 'twilio':
        return super().render(request, params=params)
    # ... existing Twilio body ...

def generate_dialplan(self, params, exten=None):
    self.ensure_one()
    if self.provider_id.code != 'twilio':
        return super().generate_dialplan(params, exten=exten)
    return ''  # Twilio agents have no FS dialplan.

@api.model
def transfer(self, channel_sid=None, exten=None):
    agent = self._resolve_transfer_agent(channel_sid)
    if not agent or agent.provider_id.code != 'twilio':
        return super().transfer(channel_sid=channel_sid, exten=exten)
    # ... existing Twilio body ...
```

`connect_elevenlabs_freeswitch/models/agent.py` is symmetric, guarded
by `'freeswitch'`.

A new helper `_resolve_transfer_agent(channel_sid)` is added on the
core EL agent model. It looks up the agent via
`connect.channel.search([('sid','=', channel_sid)]).call.elevenlabs_agent`
— the same path already used inside both Twilio and FS transfer
bodies — so the guard works under `@api.model` calls that lack a
recordset. Returns an empty recordset on failure; both bridges
super() in that case, letting the core stub log the warning.

The core stubs in `connect_elevenlabs/models/agent.py` keep the
existing "no provider bridge installed" warning — they are reached
only when `provider_id` points at a provider without an installed
EL-bridge, which is a misconfiguration.

### 6. Migration

None. `required=True` on a fresh column upgrades cleanly on databases
where `connect.elevenlabs_agent` is empty; dev installs with existing
rows either drop the DB or backfill `provider_id` by hand via
`run_odoo_shell` before the module upgrade. Production data is not
yet a concern on this branch.

The same change will need a symmetric backport to 18.0; that work is
out of scope here.

### 7. `tests_suite`

Two integration tests are added under
`tests_suite/connect_elevenlabs/tests/`:

- `test_agent_provider_default` — creating an agent without an
  explicit `provider_id` resolves to the only installed bridge when
  one bridge is present, and to Twilio when both are present.
- `test_agent_provider_pinned_after_exten` — assigning an extension
  to an agent provisions `el_virtual_number_uid`, after which
  `write({'provider_id': ...})` raises `ValidationError`.

### 8. Docs

Per project CLAUDE.md ("Documentation & Specs Maintenance"), updates
ship in the same commit:

- `docs/admin/` — short "Choosing a provider for an ElevenLabs agent"
  section (one paragraph + form screenshot).
- `specs/connect_elevenlabs.md` if present — note the new field and
  pinned-after-exten behaviour on the agent model.

## Alternatives considered

- **Add `provider_id` from each bridge module instead of the core.**
  When both bridges are installed, the field is declared by two
  `_inherit`s and Odoo merges them, which is fragile and gives no
  meaningful win over declaring once in core. Rejected.
- **M2M `provider_ids`** (multi-provider agent). Real workloads bind
  one EL agent to one carrier path; no concrete case for "the same
  agent reachable via Twilio and FS simultaneously" exists today.
  M2O is simpler, and a future M2M migration is non-breaking
  (`provider_id` becomes a computed convenience over the M2M).
  Rejected for now.
- **Dispatch via `connect.provider` instead of agent `_inherit`.**
  Cleaner in theory (the agent stays single-responsibility), but
  forces every bridge to grow a new provider method per EL operation
  (`_elevenlabs_render`, `_elevenlabs_generate_dialplan`,
  `_elevenlabs_transfer`) and rewrite both bridges in one go. The
  guarded `_inherit` pattern matches what `_originate_call` and
  `_verify_webhook` already do on `connect.provider` and keeps the
  change tight. Rejected for this iteration.
- **Auto-reprovision on `provider_id` change.** Implicit and easy to
  surprise on. The explicit "remove extension first" rule is small,
  loud, and reversible. Rejected.

## Consequences

- Agents have an explicit provider, surfaced in the form header and
  in the list view.
- Bridge-side view tabs and Python overrides only act on agents whose
  `provider_id` matches their code. Removes the silent MRO-order
  dependency on `transfer()`, `el_inbound_allowed_ips` defaults, and
  the "Twilio" tab visibility.
- `connect.provider._for_record(agent)` becomes useful.
- A dev install with existing `connect.elevenlabs_agent` rows will
  fail to upgrade until those rows get a `provider_id`. This is
  intentional — see section 6.
- 18.0 carries an unfixed version of this until the backport lands.
