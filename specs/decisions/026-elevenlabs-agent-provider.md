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

---

## Follow-up — ODU-25 (2026-05-29): two residual bugs found in live testing

After the plan above shipped, neither EL agent extension routed a call
(`freeswitch-19`). Two gaps remained:

1. **FreeSWITCH agents kept Twilio's inbound IP allow-list.** §4's
   `_default_el_inbound_allowed_ips` resolved via `_default_provider_id()`
   (which prefers Twilio) at create-time, and **nothing recomputed the
   field when the user switched `provider_id` to FreeSWITCH** in the
   form. The Twilio IP list was then provisioned onto the agent's EL
   `phone_number` inbound trunk, so EL rejected our FreeSWITCH source IP
   and returned SIP `404 UNALLOCATED_NUMBER` for `444`. (Verified:
   relaxing the EL entity to `0.0.0.0/0` made the call answer.)

   **Fix:** `el_inbound_allowed_ips` becomes a **computed-stored**
   (`@api.depends('provider_id')`, `readonly=False`) field — it tracks
   the agent's actual provider on both UI switch and programmatic
   create, resets on provider change, and preserves a manual edit until
   then. `_default_el_inbound_allowed_ips` is removed.

2. **Twilio bridge dialed a non-existent SIP host.** `twilio_sip_host`
   defaulted to `sip.elevenlabs.io`, which is **NXDOMAIN**. EL only
   terminates inbound SIP on `sip.rtc.elevenlabs.io` (TLS:5061 /
   TCP:5060; UDP unavailable — and Twilio's `<Sip>` default is UDP).
   `555` therefore never reached EL.

   **Fix:** default `twilio_sip_host` → `sip.rtc.elevenlabs.io`, and
   `render()` now emits `sip:{agent_uid}@{host}:5061;transport=tls?
   X-Call-Sid=…` (Twilio routes `;transport=tls`; it ignores the
   `sips:` scheme).

Data fix for the two already-provisioned agents (clear FS agent's
allow-list + re-sync; correct the Twilio agent's host). Versions:
`connect_elevenlabs` `1.1.14`→`1.1.15`, `connect_elevenlabs_twilio`
`1.1.3`→`1.1.4`. Tests added to
`tests_suite/connect_elevenlabs/tests/test_agent_provider.py`. Both
extensions verified end-to-end (444 via `fs_cli originate` → EL
answers; 555 TwiML validated against the resolved host/transport).

---

# Implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire an explicit `provider_id` into `connect.elevenlabs_agent`
and have every bridge-side override (render / dialplan / transfer /
inbound-IP default / view tabs) act only on agents matching its
provider code.

**Architecture:** Field + defaults on the core EL agent; provider-side
dispatch hooks (`_elevenlabs_has_bridge`, `_elevenlabs_default_inbound_ips`)
on `connect.provider`; bridge modules override the provider hooks and
guard their existing agent-side `_inherit` overrides by
`self.provider_id.code`. View inheritance conditions tabs on a related
`provider_code`.

**Tech stack:** Odoo 19, Python 3, Odoo XML views, tests via
`oduflow run_odoo_tests` against the gated `tests_suite/` submodule.

## File structure

- `connect_elevenlabs/models/agent.py` — `provider_id`,
  `provider_code` (related), `_default_provider_id`,
  `_provider_domain`, `_default_el_inbound_allowed_ips`,
  pin-on-write check, `_resolve_transfer_agent` helper.
- `connect_elevenlabs/models/provider.py` — base stubs
  `_elevenlabs_has_bridge` (returns `False`) and
  `_elevenlabs_default_inbound_ips` (returns `''`).
- `connect_elevenlabs/views/agent.xml` — radio selector in `oe_title`,
  invisible `provider_code`, list column, pin readonly.
- `connect_elevenlabs/__manifest__.py` — version bump
  `1.1.13` → `1.1.14`.
- `connect_elevenlabs_twilio/models/__init__.py` — import `provider`.
- `connect_elevenlabs_twilio/models/provider.py` *(new)* — Twilio
  overrides of `_elevenlabs_has_bridge` and
  `_elevenlabs_default_inbound_ips` (moves
  `TWILIO_SIP_SIGNALING_IPS` here).
- `connect_elevenlabs_twilio/models/agent.py` — drop
  `el_inbound_allowed_ips` redefinition and `TWILIO_SIP_SIGNALING_IPS`
  constant; guard `render()` and `transfer()` by
  `provider_id.code == 'twilio'`.
- `connect_elevenlabs_twilio/views/agent.xml` — wrap the existing
  `<page name="twilio">` with
  `invisible="provider_code != 'twilio'"`.
- `connect_elevenlabs_twilio/__manifest__.py` — version bump
  `1.1.2` → `1.1.3`.
- `connect_elevenlabs_freeswitch/models/__init__.py` — import
  `provider`.
- `connect_elevenlabs_freeswitch/models/provider.py` *(new)* — FS
  overrides of `_elevenlabs_has_bridge` and
  `_elevenlabs_default_inbound_ips` (returns `''`).
- `connect_elevenlabs_freeswitch/models/agent.py` — guard
  `generate_dialplan()` and `transfer()` by
  `provider_id.code == 'freeswitch'`.
- `connect_elevenlabs_freeswitch/__manifest__.py` — version bump
  `1.1.4` → `1.1.5`.
- `tests_suite/connect_elevenlabs/tests/test_agent_provider.py`
  *(new)* — `test_agent_provider_default`,
  `test_agent_provider_pinned_after_exten`.
- `docs/admin/elevenlabs-setup.md` — append a short subsection
  "Choosing a provider for an agent".

---

### Task 1: Provider-side hooks on `connect.provider`

**Files:**
- Modify: `connect_elevenlabs/models/provider.py`

- [ ] **Step 1: Extend the existing `ElevenLabsProvider` model with two new dispatch stubs.**

In `connect_elevenlabs/models/provider.py`, append inside the class
(after `_verify_webhook`):

```python
    # ------------------------------------------------------------------
    # ElevenLabs agent dispatch hooks (ADR-026)
    # ------------------------------------------------------------------

    def _elevenlabs_has_bridge(self):
        """Return True if this provider has an installed EL bridge
        (connect_elevenlabs_twilio / connect_elevenlabs_freeswitch / …).

        Base implementation: False. Each bridge module overrides for
        its own code via the usual `if self.code != 'xxx': return
        super()._elevenlabs_has_bridge(); return True` pattern."""
        return False

    def _elevenlabs_default_inbound_ips(self):
        """Default value for `connect.elevenlabs_agent.el_inbound_allowed_ips`
        when this provider is selected. Base: empty string (allow-all).
        Twilio bridge returns the Twilio SIP signaling range; FS bridge
        returns ''."""
        return ''
```

- [ ] **Step 2: Commit.**

```bash
git add connect_elevenlabs/models/provider.py
git commit -m "[connect_elevenlabs] add provider dispatch hooks for agent provider_id (ODU-24)"
```

---

### Task 2: `provider_id` field + defaults on `connect.elevenlabs_agent`

**Files:**
- Modify: `connect_elevenlabs/models/agent.py`
- Modify: `connect_elevenlabs/__manifest__.py`

- [ ] **Step 1: Add field definitions on `ElevenlabsAgent`.**

In `connect_elevenlabs/models/agent.py`, insert above the existing
`name = fields.Char(required=True)` line:

```python
    provider_id = fields.Many2one(
        'connect.provider',
        string='Provider',
        required=True,
        ondelete='restrict',
        default=lambda self: self._default_provider_id(),
        domain=lambda self: self._provider_domain(),
        help='Telephony provider that delivers calls to this '
             'ElevenLabs agent (SIP bridge + transfer back-channel).',
    )
    provider_code = fields.Char(
        related='provider_id.code', store=False, readonly=True,
        string='Provider code',
    )
```

- [ ] **Step 2: Add the default resolver and domain function on the class (anywhere below the field block; keep near `_compute_has_transfer_tool`).**

```python
    @api.model
    def _default_provider_id(self):
        Provider = self.env['connect.provider'].sudo()
        eligible = Provider.search([]).filtered(
            lambda p: p._elevenlabs_has_bridge())
        if not eligible:
            return False
        twilio = eligible.filtered(lambda p: p.code == 'twilio')
        return twilio.id if twilio else eligible[0].id

    @api.model
    def _provider_domain(self):
        Provider = self.env['connect.provider'].sudo()
        eligible = Provider.search([]).filtered(
            lambda p: p._elevenlabs_has_bridge())
        return [('id', 'in', eligible.ids)]
```

- [ ] **Step 3: Bump the manifest.**

In `connect_elevenlabs/__manifest__.py` change `'version': '1.1.13'`
to `'version': '1.1.14'`.

- [ ] **Step 4: Deploy and confirm the model loads.**

Run: `mcp__oduflow__pull_and_apply env_name=freeswitch-19`
Expected: `connect_elevenlabs` upgrades cleanly; no traceback in
upgrade logs; `connect.elevenlabs_agent` keeps loading. Existing
records may exist with `provider_id IS NULL` — the upgrade itself
does not fail because Odoo does not retroactively enforce
`required=True` on an existing column when adding a Many2one; new
records will be required to fill it.

If the env DB has stale agents with no provider, the user opens
`run_odoo_shell` and runs:

```python
twilio = env['connect.provider'].sudo().search([('code','=','twilio')])
agents = env['connect.elevenlabs_agent'].sudo().with_context(
    skip_elevenlabs=True).search([('provider_id', '=', False)])
agents.write({'provider_id': twilio.id})
env.cr.commit()
```

- [ ] **Step 5: Commit.**

```bash
git add connect_elevenlabs/models/agent.py connect_elevenlabs/__manifest__.py
git commit -m "[connect_elevenlabs] add provider_id on elevenlabs_agent (ODU-24)"
```

---

### Task 3: Move `el_inbound_allowed_ips` default to provider dispatch

**Files:**
- Modify: `connect_elevenlabs/models/agent.py`
- Modify: `connect_elevenlabs_twilio/models/agent.py`
- Create: `connect_elevenlabs_twilio/models/provider.py`
- Modify: `connect_elevenlabs_twilio/models/__init__.py`
- Create: `connect_elevenlabs_freeswitch/models/provider.py`
- Modify: `connect_elevenlabs_freeswitch/models/__init__.py`

- [ ] **Step 1: On core EL agent, change `el_inbound_allowed_ips` to use a defaulter that delegates to the provider.**

In `connect_elevenlabs/models/agent.py`, replace the existing
`el_inbound_allowed_ips = fields.Text(...)` line with:

```python
    el_inbound_allowed_ips = fields.Text(
        string="Inbound Allowed IPs",
        default=lambda self: self._default_el_inbound_allowed_ips(),
        help="IP addresses or CIDR ranges (comma- or newline-separated) "
             "ElevenLabs will accept inbound SIP INVITEs from. Empty allows all.",
    )
```

And add the defaulter near `_default_provider_id`:

```python
    @api.model
    def _default_el_inbound_allowed_ips(self):
        provider_id = self._context.get('default_provider_id') \
            or self._default_provider_id()
        if not provider_id:
            return ''
        provider = self.env['connect.provider'].sudo().browse(provider_id)
        return provider._elevenlabs_default_inbound_ips()
```

- [ ] **Step 2: Create `connect_elevenlabs_twilio/models/provider.py`.**

```python
"""Twilio bridge provider hooks (ADR-026)."""
from odoo import models


TWILIO_SIP_SIGNALING_IPS = (
    "54.172.60.0/23",
    "54.244.51.0/24",
    "54.171.127.192/30",
    "35.156.191.128/25",
    "35.162.40.0/23",
    "54.65.63.192/26",
    "54.169.127.128/26",
    "54.252.254.64/26",
    "177.71.206.192/26",
)


class ConnectProvider(models.Model):
    _inherit = 'connect.provider'

    def _elevenlabs_has_bridge(self):
        if self.code != 'twilio':
            return super()._elevenlabs_has_bridge()
        return True

    def _elevenlabs_default_inbound_ips(self):
        if self.code != 'twilio':
            return super()._elevenlabs_default_inbound_ips()
        return "\n".join(TWILIO_SIP_SIGNALING_IPS)
```

- [ ] **Step 3: Import provider in `connect_elevenlabs_twilio/models/__init__.py`.**

The current file is just `from . import agent`. Add a `provider`
import above it:

```python
from . import provider
from . import agent
```

- [ ] **Step 4: Drop the Twilio-side field redefinition and constant.**

In `connect_elevenlabs_twilio/models/agent.py`:

- Delete the leading three-line comment "Twilio SIP signaling IP
  ranges…" together with the `TWILIO_SIP_SIGNALING_IPS = (...)` tuple
  declaration. (This block sits between the imports and the
  `class ElevenlabsAgent` line.)
- Inside the class, delete the `el_inbound_allowed_ips =
  fields.Text(default="\n".join(TWILIO_SIP_SIGNALING_IPS))` block.

What remains in the class is the `twilio_sip_host` field, plus the
`render` / `transfer` methods (those get guarded in Task 4).

- [ ] **Step 5: Create `connect_elevenlabs_freeswitch/models/provider.py`.**

```python
"""FreeSWITCH bridge provider hooks (ADR-026)."""
from odoo import models


class ConnectProvider(models.Model):
    _inherit = 'connect.provider'

    def _elevenlabs_has_bridge(self):
        if self.code != 'freeswitch':
            return super()._elevenlabs_has_bridge()
        return True

    def _elevenlabs_default_inbound_ips(self):
        if self.code != 'freeswitch':
            return super()._elevenlabs_default_inbound_ips()
        return ''
```

- [ ] **Step 6: Import provider in `connect_elevenlabs_freeswitch/models/__init__.py`.**

```python
from . import provider
from . import agent
```

- [ ] **Step 7: Commit.**

```bash
git add connect_elevenlabs/models/agent.py \
        connect_elevenlabs_twilio/models/__init__.py \
        connect_elevenlabs_twilio/models/provider.py \
        connect_elevenlabs_twilio/models/agent.py \
        connect_elevenlabs_freeswitch/models/__init__.py \
        connect_elevenlabs_freeswitch/models/provider.py
git commit -m "[misc] EL agent inbound-IP default routed via provider hook (ODU-24)"
```

---

### Task 4: `_resolve_transfer_agent` + dispatch guards

**Files:**
- Modify: `connect_elevenlabs/models/agent.py`
- Modify: `connect_elevenlabs_twilio/models/agent.py`
- Modify: `connect_elevenlabs_freeswitch/models/agent.py`

- [ ] **Step 1: Add `_resolve_transfer_agent` on core EL agent.**

In `connect_elevenlabs/models/agent.py`, near `_resolve_transfer_target`:

```python
    @api.model
    def _resolve_transfer_agent(self, channel_sid):
        """Return the connect.elevenlabs_agent that owns the given
        FS/Twilio channel SID, or empty recordset. Used by bridge
        modules to gate `@api.model` transfer() by provider_id.code."""
        if not channel_sid:
            return self.browse()
        channel = self.env['connect.channel'].sudo().search(
            [('sid', '=', channel_sid)], limit=1)
        return channel.call.elevenlabs_agent if channel and channel.call else self.browse()
```

- [ ] **Step 2: Guard Twilio `render()` and `transfer()`.**

In `connect_elevenlabs_twilio/models/agent.py`, wrap each method's
existing body in a provider guard. `render`:

```python
    def render(self, request, params=None):
        self.ensure_one()
        if self.provider_id.code != 'twilio':
            return super().render(request, params=params)
        if not self.env['oduist.license'].check_license('connect_elevenlabs'):
            return (
                "<Response><Pause length='1'/>"
                "<Say>This is Oduist Connect. Your trial period is over. "
                "Please buy a license to continue.</Say>"
                "<Pause length='1'/></Response>"
            )
        channel_sid = request.get('CallSid')
        host = self.twilio_sip_host or 'sip.elevenlabs.io'
        response = VoiceResponse()
        dial = Dial()
        dial.sip(f"sip:{self.agent_uid}@{host}?X-Call-Sid={channel_sid}")
        response.append(dial)
        debug(self, pretty_xml(response))
        return response
```

`transfer`:

```python
    @api.model
    def transfer(self, channel_sid=None, exten=None):
        agent = self._resolve_transfer_agent(channel_sid)
        if not agent or agent.provider_id.code != 'twilio':
            return super().transfer(channel_sid=channel_sid, exten=exten)
        logger.info("Transfer request: exten=%s, channel_sid=%s", exten, channel_sid)
        if not channel_sid or not exten:
            return "Not all parameters passed. You must provide channel_sid and exten (only digits)"
        exten_rec, err = agent._resolve_transfer_target(exten)
        if err:
            return err
        client = self.env['connect.provider.twilio.config'].sudo().get_client()
        channel = self.env['connect.channel'].search([('sid', '=', channel_sid)])
        twiml = exten_rec.render(
            {"Caller": channel.caller, "Called": channel.called, "CallSid": channel.sid}
        )
        debug(agent, "Transfer to: {}".format(pretty_xml(twiml)))
        client.calls(channel_sid).update(twiml=twiml)
        return "Transfer Successful"
```

- [ ] **Step 3: Guard FS `generate_dialplan()` and `transfer()`.**

In `connect_elevenlabs_freeswitch/models/agent.py`:

```python
    def generate_dialplan(self, params, exten=None):
        self.ensure_one()
        if self.provider_id.code != 'freeswitch':
            return super().generate_dialplan(params, exten=exten)
        if not exten:
            logger.warning(
                "generate_dialplan called for agent %s without exten", self.id)
            return ''
        if not self.agent_uid:
            logger.warning(
                "Agent %s has no agent_uid; cannot bridge", self.id)
            return ''
        if not self.el_virtual_number_uid:
            logger.warning(
                "Agent %s has no el_virtual_number_uid; cannot route to EL. "
                "Has an extension been assigned?", self.id)
            return ''
        Template = self.env['connect.freeswitch.template'].sudo()
        return Template.render('dialplan_elevenlabs_sip', {
            'extension_number': exten.number,
            'agent_uid': self.agent_uid,
            'el_virtual_number_uid': self.el_virtual_number_uid,
        })

    @api.model
    def transfer(self, channel_sid=None, exten=None):
        agent = self._resolve_transfer_agent(channel_sid)
        if not agent or agent.provider_id.code != 'freeswitch':
            return super().transfer(channel_sid=channel_sid, exten=exten)
        logger.info("FS transfer request: exten=%s, channel_sid=%s", exten, channel_sid)
        if not channel_sid or not exten:
            return ("Not all parameters passed. You must provide "
                    "channel_sid and exten (only digits)")
        exten_rec, err = agent._resolve_transfer_target(exten)
        if err:
            return err
        channel = self.env['connect.channel'].search(
            [('sid', '=', channel_sid)], limit=1)
        if not channel:
            return "Channel %s not found" % channel_sid
        result = self.env['connect.settings'].freeswitch_api(
            'uuid_transfer',
            '{} {} XML default'.format(channel.sid, exten_rec.number))
        if result is False:
            return "FreeSWITCH transfer failed (XML-RPC unreachable)"
        return "Transfer Successful"
```

- [ ] **Step 4: Commit.**

```bash
git add connect_elevenlabs/models/agent.py \
        connect_elevenlabs_twilio/models/agent.py \
        connect_elevenlabs_freeswitch/models/agent.py
git commit -m "[misc] EL bridges: guard render/dialplan/transfer by provider_id.code (ODU-24)"
```

---

### Task 5: Pin `provider_id` after extension provisioning

**Files:**
- Modify: `connect_elevenlabs/models/agent.py`

- [ ] **Step 1: Extend `write()` to reject provider changes after provisioning.**

In `connect_elevenlabs/models/agent.py`, at the very top of the
existing `write()` method (before the `if 'exten' in vals:` line),
insert:

```python
        if 'provider_id' in vals:
            for rec in self:
                if rec.el_virtual_number_uid or rec.exten:
                    raise ValidationError(
                        "Cannot change provider on an agent with an "
                        "active extension. Remove the extension first."
                    )
```

- [ ] **Step 2: Commit.**

```bash
git add connect_elevenlabs/models/agent.py
git commit -m "[connect_elevenlabs] pin agent provider_id once extension is assigned (ODU-24)"
```

---

### Task 6: View changes (form radio, list column, conditional Twilio tab)

**Files:**
- Modify: `connect_elevenlabs/views/agent.xml`
- Modify: `connect_elevenlabs_twilio/views/agent.xml`
- Modify: `connect_elevenlabs_twilio/__manifest__.py`

- [ ] **Step 1: Add `provider_id` and `provider_code` to the core form.**

In `connect_elevenlabs/views/agent.xml`, replace the existing block

```xml
                    <div class="oe_title">
                        <h1>
                            <label class="oe_edit_only" for="name"/>
                            <field name="name" placeholder="Agent name..."/>
                        </h1>
                    </div>
```

with

```xml
                    <div class="oe_title">
                        <h1>
                            <label class="oe_edit_only" for="name"/>
                            <field name="name" placeholder="Agent name..."/>
                        </h1>
                        <group>
                            <field name="provider_id" widget="radio"
                                   options="{'horizontal': true}"
                                   readonly="exten or el_virtual_number_uid"/>
                            <field name="provider_code" invisible="1"/>
                        </group>
                    </div>
```

- [ ] **Step 2: Add a `provider_id` column to the list view.**

In the same file, replace the existing list-view block

```xml
            <list>
                <field name="name"/>
                <field name="llm"/>
                <field name="voice"/>
                <field name="language" optional="show"/>
                <field name="additional_languages" widget="many2many_tags" optional="show"/>
                <field name="exten_number" string="Exten"/>
            </list>
```

with

```xml
            <list>
                <field name="name"/>
                <field name="provider_id" optional="show"/>
                <field name="llm"/>
                <field name="voice"/>
                <field name="language" optional="show"/>
                <field name="additional_languages" widget="many2many_tags" optional="show"/>
                <field name="exten_number" string="Exten"/>
            </list>
```

- [ ] **Step 3: Make the Twilio tab provider-conditional.**

In `connect_elevenlabs_twilio/views/agent.xml`, change
`<page name="twilio" string="Twilio">` to
`<page name="twilio" string="Twilio" invisible="provider_code != 'twilio'">`.

- [ ] **Step 4: Bump the Twilio bridge manifest.**

In `connect_elevenlabs_twilio/__manifest__.py` change
`'version': '1.1.2'` to `'version': '1.1.3'`.

- [ ] **Step 5: Commit.**

```bash
git add connect_elevenlabs/views/agent.xml \
        connect_elevenlabs_twilio/views/agent.xml \
        connect_elevenlabs_twilio/__manifest__.py
git commit -m "[misc] EL agent form: provider selector + conditional Twilio tab (ODU-24)"
```

---

### Task 7: Tests (gated suite)

**Files:**
- Create: `tests_suite/connect_elevenlabs/tests/test_agent_provider.py`

**Branch policy (ODU-24 decision):** the submodule work for this
change goes on `tests_suite`'s `19.0-twilio-fs-compat` branch
(symmetric with the main repo's feature branch), not the
submodule's default `19.0`. It is merged into `19.0` together with
the main repo's merge of `19.0-twilio-fs-compat`.

- [ ] **Step 0: Switch the submodule to the feature branch.**

```bash
cd tests_suite
git fetch origin
git checkout 19.0-twilio-fs-compat  # creates from origin/19.0-twilio-fs-compat if needed
# Bring it up to date with submodule's 19.0 tip so prior tests are present.
git merge --ff-only origin/19.0 || git merge origin/19.0
cd ..
```

- [ ] **Step 1: Write the two integration tests.**

```python
# tests_suite/connect_elevenlabs/tests/test_agent_provider.py
"""ADR-026 — provider_id on connect.elevenlabs_agent."""
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('-at_install', 'post_install', 'connect_elevenlabs')
class TestAgentProvider(TransactionCase):

    def _make_voice(self):
        return self.env['connect.elevenlabs_voice'].create({
            'name': 'TestVoice',
            'voice_id': 'voice-test-1',
        })

    def _make_agent(self, **vals):
        defaults = {
            'name': 'Agent Under Test',
            'voice': self._make_voice().id,
            'prompt': 'You are a test.',
            'additional_languages': [],
        }
        defaults.update(vals)
        return self.env['connect.elevenlabs_agent'].with_context(
            skip_elevenlabs=True).create(defaults)

    def test_agent_provider_default(self):
        """Default `provider_id` resolves to Twilio when both bridges
        are installed (matches `_default_provider_id` rule)."""
        Provider = self.env['connect.provider'].sudo()
        twilio = Provider.search([('code', '=', 'twilio')])
        self.assertTrue(twilio, "Twilio provider must be registered")
        agent = self._make_agent()
        self.assertEqual(
            agent.provider_id, twilio,
            "Default must be Twilio when both bridges are installed",
        )
        self.assertEqual(agent.provider_code, 'twilio')

    def test_agent_provider_pinned_after_exten(self):
        """Changing provider_id after extension assignment raises."""
        Provider = self.env['connect.provider'].sudo()
        twilio = Provider.search([('code', '=', 'twilio')])
        fs = Provider.search([('code', '=', 'freeswitch')])
        agent = self._make_agent(provider_id=twilio.id)
        # Simulate provisioning: set el_virtual_number_uid bypass-style.
        agent.with_context(skip_el_sync=True).el_virtual_number_uid = 'phnum_test'
        with self.assertRaises(ValidationError):
            agent.write({'provider_id': fs.id})
```

- [ ] **Step 2: Run the test.**

```bash
mcp__oduflow__run_odoo_tests module=connect_elevenlabs
```

Expected: both `test_agent_provider_default` and
`test_agent_provider_pinned_after_exten` pass.

- [ ] **Step 3: Commit and push (inside `tests_suite/`).**

```bash
cd tests_suite
git add connect_elevenlabs/tests/test_agent_provider.py
git commit -m "connect_elevenlabs: add agent provider_id tests (ODU-24)"
git push -u origin 19.0-twilio-fs-compat
cd ..
# Bump the submodule pointer in the main repo's feature branch.
git add tests_suite
git commit -m "[misc] bump tests_suite submodule for ODU-24"
```

---

### Task 8: FreeSWITCH bridge version bump + redeploy

**Files:**
- Modify: `connect_elevenlabs_freeswitch/__manifest__.py`

- [ ] **Step 1: Bump the FS bridge manifest.**

In `connect_elevenlabs_freeswitch/__manifest__.py` change
`'version': '1.1.4'` to `'version': '1.1.5'`.

- [ ] **Step 2: Commit.**

```bash
git add connect_elevenlabs_freeswitch/__manifest__.py
git commit -m "[connect_elevenlabs_freeswitch] bump for agent provider_id (ODU-24)"
```

- [ ] **Step 3: Push, then pull-and-apply on `freeswitch-19`.**

```bash
git push
```

Then in the chat: `mcp__oduflow__pull_and_apply env_name=freeswitch-19`.

Expected: `connect_elevenlabs`, `connect_elevenlabs_twilio`,
`connect_elevenlabs_freeswitch` all upgrade; restart logs show no
traceback; module loading lists the three modules.

---

### Task 9: Manual UI verification via `agent-browser`

- [ ] **Step 1: Reset admin password on `freeswitch-19`.**

`mcp__oduflow__reset_admin_password env_name=freeswitch-19`

- [ ] **Step 2: Open Connect → ElevenLabs → Agents.**

Open the env URL (`http://localhost:50002/web?debug=1`), login
`admin` / `test`, navigate to the Agents list. Expected: a new
`Provider` column is visible; existing agents have it filled (or you
filled it by hand per Task 2 Step 4).

- [ ] **Step 3: Open one agent's form.**

Expected:
- Radio selector "Provider" sits in the header next to the name.
- For a Twilio agent: the "Twilio" notebook tab is visible.
- Switch the radio to FreeSWITCH (if the agent has no extension):
  the "Twilio" tab disappears; saving works.
- If the agent has an extension: the radio is readonly; trying to
  save a change via `write` from `run_odoo_shell` raises
  `ValidationError`.

- [ ] **Step 4: Create a fresh agent.**

Click "New" — `provider_id` is preselected (Twilio by default) and
`el_inbound_allowed_ips` is prefilled with the Twilio signaling
range. Switch the radio to FreeSWITCH before saving — the
allow-list resets to empty. Save and confirm.

---

### Task 10: Documentation

**Files:**
- Modify: `docs/admin/elevenlabs-setup.md`

- [ ] **Step 1: Append a short subsection at the end of `docs/admin/elevenlabs-setup.md`.**

```markdown
## Choosing a provider for an agent

Each ElevenLabs agent must be bound to one telephony provider — the
one that routes calls to it. Pick the provider in the agent form
header. Twilio agents accept inbound SIP from Twilio's signaling
range by default; FreeSWITCH agents allow all by default — restrict
this in production via the *SIP Routing* tab.

The provider is locked once you assign an extension to the agent.
To switch provider on an existing agent, first remove the extension,
change the provider, then re-assign an extension.
```

- [ ] **Step 2: Commit.**

```bash
git add docs/admin/elevenlabs-setup.md
git commit -m "[misc] docs: choosing a provider for an EL agent (ODU-24)"
```

---

### Task 11: Close the loop on Linear

- [ ] **Step 1: Push all commits.**

```bash
git push
```

- [ ] **Step 2: Mark ODU-24 Done with a final comment.**

Update via `mcp__plugin_linear_linear__save_issue id=ODU-24
state=Done`, then `save_comment issueId=ODU-24` with the commit
hashes and a one-line summary ("Implemented per ADR-026: provider_id
on connect.elevenlabs_agent, bridge dispatch guards, pinned after
exten, tests in tests_suite, docs updated.").
