# ADR-023: Multi-provider architecture for telephony backends

**Status:** Proposed
**Date:** 2026-05-25
**Builds on:** ADR-011 (gated test suite), ADR-015 (firewall token controllers)
**Related:** `specs/architecture.md` (the technology-agnostic-core principle)

## Context

The `connect/` core was designed as technology-agnostic: every provider
(Twilio, FreeSWITCH, ElevenLabs) was supposed to plug in via
`_inherit` and override a small set of abstract methods. In practice
the contract was never formalised, and the audit of
`connect_twilio` + `connect_freeswitch` coexistence on branch
`19.0-twilio-fs-compat` (env `freeswitch-19`) exposed systemic gaps:

1. **Required fields leak into core.** `connect.user.username`,
   `connect.user.domain`, `connect.user.twilio_edge`,
   `connect.user.sip_priority`, `connect.user.client_priority` are
   declared with `required=True` by `connect_twilio` even though
   FreeSWITCH-only users have no use for them. Creating a user on a
   mixed-install DB is awkward; pure-FS deploys carry dead required
   slots; future third providers cannot opt out.

2. **Method dispatch is implicit (last-MRO-wins).** Core calls
   `connect.message.send()`, `connect.call.originate_call()`,
   `connect.callflow.render()`, `connect.exten.render()` and trusts
   that exactly one provider has overridden each. When two are
   installed, the module loaded later silently wins. There is no
   per-record routing ("this callflow renders to TwiML, that one to
   FS XML") because there is no per-record provider attribute.

3. **Unguarded provider API calls in `res.users` create/write/unlink.**
   `connect_twilio.models.user` unconditionally talks to the Twilio
   REST API on every user lifecycle event; pure-FS installs need a
   `no_twilio_create` context guard to even create a user.

4. **Frontend double-registers systray/services.** Both
   `connect_twilio/static/.../phone/*` and
   `connect_freeswitch/static/.../phone_service.js` register their
   own `PhoneSystray` + `PhonePanel` + `phone` service in the global
   Odoo registry unconditionally. Two trays, two popups, two
   `active_calls` services, two sets of mail message actions.

5. **`get_webrtc_config()` returns one provider's config.**
   `connect_freeswitch` returns Verto credentials from
   `/connect/webrtc/config`; if Twilio Voice JS needs its own config
   from the same endpoint, the second provider has nowhere to plug in.

6. **`Settings` is one flat record.** Each provider adds 10–25 fields
   directly on `connect.settings`. At 2 providers the UI is already
   cluttered; at 3+ it is unworkable. The notebook in
   `connect/views/settings.xml` has no named extension anchors, so
   provider tab order is install-order accidental.

7. **No `connect.provider` registry.** The string
   `'twilio'` / `'freeswitch'` exists nowhere as a first-class
   entity. There is no way to query "which providers are installed,"
   "which provider owns this call," "which providers is this user
   provisioned on."

8. **Selection-extension on shared enums.** `connect.number.destination`
   gets `fs_fifo` appended by FS; Twilio appends its own;
   ElevenLabs appends `el_agent`. Cross-provider mental model
   collapses; views break on uninstall.

These are not bugs in any one module — they are gaps in the **core
contract**. Adding a third provider today would require either
patching core or accepting a third layer of last-MRO-wins.

Audit findings are documented in the session log; the count is ~38
items in Twilio and ~40 in FreeSWITCH that touch shared surfaces, of
which 6 are hard blockers for simultaneous operation.

## Decision

Formalise "provider" as a first-class core concept and route every
provider-specific operation through an explicit registry + per-record
binding, rather than through Python MRO.

The design has six pillars. Phases 1–7 below sequence the rollout
without ever shipping a half-broken state.

### Pillar 1 — `connect.provider` registry (new core model)

```python
class ConnectProvider(models.Model):
    _name = 'connect.provider'
    _description = 'Telephony provider'
    _order = 'sequence, code'

    code     = fields.Char(required=True)          # 'twilio', 'freeswitch'
    name     = fields.Char(required=True)          # 'Twilio', 'FreeSWITCH'
    sequence = fields.Integer(default=10)
    active   = fields.Boolean(default=True)
    config_model = fields.Char()                   # 'connect.provider.twilio.config'

    _sql_constraints = [('code_uniq', 'UNIQUE(code)', '…')]
```

Each provider module's `post_init_hook` creates its own record
(idempotent on `code`). `uninstall_hook` deactivates it. Core
exposes:

- `connect.provider._for_user(user)` — Many2many lookup, see Pillar 2
- `connect.provider._for_record(record)` — reads `record.provider_id`
- `connect.provider._default()` — sequence-ordered first active

### Pillar 2 — per-record provider binding

Add an optional `provider_id` Many2one to provider on:

| Model            | Field            | Semantics                       |
|------------------|------------------|---------------------------------|
| `connect.call`   | `provider_id`    | which provider actually handled |
| `connect.number` | `provider_id`    | DID ownership                   |
| `connect.callflow` | `provider_id`  | which `render()` to dispatch    |
| `connect.exten`  | `provider_id`    | same                            |

For `connect.user`, a single Many2one is wrong (one user can be
reachable on Twilio Voice JS *and* a FreeSWITCH SIP extension at the
same time). Introduce a link model:

```python
class ConnectUserProviderBinding(models.Model):
    _name = 'connect.user.provider.binding'
    user_id     = fields.Many2one('connect.user', required=True, ondelete='cascade')
    provider_id = fields.Many2one('connect.provider', required=True, ondelete='cascade')
    config      = fields.Json()         # per-(user, provider) free-form
    _sql_constraints = [('uniq', 'UNIQUE(user_id, provider_id)', '…')]
```

Twilio-specific fields (`username`, `domain`, `twilio_edge`,
`sip_priority`, `client_priority`, `sip_ring_timeout`,
`client_ring_timeout`) and FS-specific fields
(`webrtc_password`, `originate_ring`, `phone_display_mode`,
`webrtc_enabled`) move off `connect.user` into provider-specific
extensions of the binding model (see Pillar 3).

### Pillar 3 — per-provider settings + per-binding extensions

Replace flat `connect.settings` provider fields with:

```python
class ConnectProviderTwilioConfig(models.Model):
    _name = 'connect.provider.twilio.config'
    _description = 'Twilio provider configuration (singleton)'
    # account_sid, auth_token, twilio_edge, twilio_region, ...
```

…and the per-user-per-provider extension:

```python
class ConnectUserProviderBindingTwilio(models.Model):
    _inherit = 'connect.user.provider.binding'
    # adds twilio_username, twilio_domain_id, twilio_edge, …
    # all required=True is fine here — the row exists *only*
    # when this user is bound to Twilio
```

Same shape for FS: `connect.provider.freeswitch.config`,
`connect.user.provider.binding` extended with WebRTC fields.

### Pillar 4 — explicit method dispatch

Core defines provider methods on `connect.provider`, not on the
domain models:

```python
class ConnectProvider(models.Model):
    _name = 'connect.provider'

    def _originate_call(self, call, ...):
        raise NotImplementedError(f'{self.code} has no _originate_call')

    def _send_message(self, message): ...
    def _render_callflow(self, callflow, params): ...
    def _render_exten(self, exten, params): ...
    def _get_webrtc_config(self, user): ...
```

`connect_twilio` does:

```python
class TwilioProvider(models.Model):
    _inherit = 'connect.provider'

    def _originate_call(self, call, ...):
        if self.code != 'twilio':
            return super()._originate_call(call, ...)
        # Twilio implementation
```

Domain models lose their direct overrides and gain a thin façade:

```python
class ConnectCall(models.Model):
    _name = 'connect.call'

    def originate(self, ...):
        provider = self.provider_id or self.env['connect.provider']._default()
        return provider._originate_call(self, ...)
```

The `if self.code != 'twilio': return super()` pattern means each
provider's method only matches when *it* is the dispatch target;
others delegate up the chain. No more last-MRO-wins.

### Pillar 5 — unified frontend phone widget

Core ships `connect.PhoneSystray` (single registry registration).
Each provider ships an *adapter*, registered into a new
`connect.phone_adapters` registry keyed by provider code, not into
Odoo's global `systray` registry.

```js
// connect/static/.../phone_systray.js
import { registry } from "@web/core/registry";
registry.category("systray").add("connect.phone", { Component: PhoneSystray });

// connect_twilio/static/.../adapter.js
import { phoneAdapters } from "@connect/services/phone_adapters";
phoneAdapters.add("twilio", TwilioPhoneAdapter);
```

The single systray icon picks the active adapter based on the
user's `connect.user.provider_ids` ∩ active providers, with a UI
toggle when more than one is available. Same pattern for the
`active_calls` tray and the mail-message message actions.

### Pillar 6 — typed extension on `Selection` enums

`connect.number.destination` becomes a stable core enum
(`'user' | 'callflow' | 'provider'`) plus a `destination_provider_id`
Many2one and a `destination_ref` Reference. Provider-specific
destinations (`fs_fifo`, future `aws_connect_queue`, etc.) live as
sub-selection inside the provider, not on the core enum.

### Pillar 7 — provider-owned UI sections

Provider-specific data models live under a provider-owned root
menu, not under a shared "Telephony / Configuration" tree. The core
menu owns only technology-agnostic resources; everything else moves
under the provider that needs it.

| Menu root              | Belongs to     | Contents (examples)                                                          |
|------------------------|----------------|------------------------------------------------------------------------------|
| Connect (core)         | `connect`      | Calls, Channels, Recordings, Users, Numbers (provider-agnostic), Settings    |
| FreeSWITCH             | `connect_freeswitch` | XML Templates, FIFO Queues, Endpoints, Gateways, Firewall              |
| Twilio                 | `connect_twilio`     | Domains, TwiML apps, Outgoing CallerIDs, WhatsApp Senders, Message Templates |
| ElevenLabs             | `connect_elevenlabs` | Agents, Voices, Tools, Agent Templates                                 |

The model `connect.fs_template` (Jinja2 dialplan templates) is the
canonical example: it has no Twilio or EL analogue and never will.
Its menu item belongs under "FreeSWITCH → XML Templates," not under
some shared "Telephony → Templates" pseudo-section. Same for
`connect.fs_fifo`, `connect.freeswitch.gateway`, the firewall
models, the WhatsApp sender, etc.

Benefits:
- Uninstalling a provider also uninstalls its menu — no orphaned
  items pointing at non-existent models.
- A pure-FS deploy doesn't see Twilio menus and vice versa.
- A 3rd provider knows where to put its UI without asking core to
  expand the shared menu.
- Admins immediately see what's provider-specific vs shared.

Implementation: each provider declares its menu root in its own
`views/menu.xml` (most already do — formalising the convention,
not inventing it). Core does not declare a parent "providers" menu;
roots are siblings.

## Phased rollout

The architecture above is large. Phases are designed so that each
ships independently, leaves the system in a working state, and can
be paused.

**Phase 0 — this ADR.** No code. Approve direction.

**Phase 1 — coexistence quick-fixes.** Smallest possible patch to
make both modules livable today, without the new architecture:
- Drop `required=True` from `connect.user.username`,
  `connect.user.domain`, `connect.user.twilio_edge`,
  `connect.user.sip_priority`, `connect.user.client_priority` (Twilio).
- Guard `res.users.create/write/unlink` Twilio API calls behind a
  `settings.account_sid` check, not just the context flag.
- Add `uninstall_hook` to `connect_freeswitch` (clear firewall
  service token, drop firewall API routes).
- Soft-rename frontend systray entries so two icons at least carry
  distinguishing labels (`Phone (Twilio)` / `Phone (FreeSWITCH)`).
Migration: NULL-ifying existing required fields is a one-shot
`ALTER COLUMN … DROP NOT NULL` per affected column.
Risk: low. Reversible.

**Phase 2 — `connect.provider` registry + `provider_id` on call/number.**
Introduce the new model and the optional Many2one on
`connect.call`, `connect.number`, `connect.callflow`,
`connect.exten`. Backfill on `post_init_hook`: existing rows get
`provider_id` set to the first active provider matching
heuristics (TwilioSid present → Twilio, FS UUID present → FS, else
NULL). No behavioural change yet — fields are read by no one.
Risk: medium (large data write on upgrade). Reversible.

**Phase 3 — dispatch via provider methods.** Move `originate_call`,
`send`, `render` from domain-model overrides into provider methods,
and add the thin façade. Old overrides remain as `super()` fallbacks
during the deprecation window so previously-deployed callers still
work. Once façade is the only entry point, drop the legacy overrides.
Risk: medium. Heavy on test coverage — Phase 3 should not ship without
the gated test suite green.

**Phase 4 — link-table for user-provider binding.** Largest, most
sensitive phase. Migration script reads each `connect.user` and
creates a `connect.user.provider.binding` row per detected provider,
moves Twilio fields into the Twilio-extended binding, drops them
from `connect.user`. Old field accessors stay as
`@api.depends('provider_binding_ids')` computed shims for one
release cycle to avoid breaking external integrations.
Risk: high. Touches existing user data; needs a dry-run mode and a
rollback path. Likely warrants its own ADR (ADR-024) with the
migration script in detail.

**Phase 5 — unified phone widget.** Frontend refactor. Independent
of Phases 2–4 once dispatch is per-provider — adapters can read
`connect.user.provider_ids` over RPC.
Risk: medium. Touches UI most users see daily; ship behind a feature
flag if possible.

**Phase 6 — per-provider settings sub-models.** Move provider-specific
settings off `connect.settings` into `connect.provider.<code>.config`.
Add named anchors in the settings view
(`<separator name="providers_anchor"/>`). Provider views target the
anchor, ordering follows `connect.provider.sequence`.
Risk: low.

**Phase 7 — typed destination + extension polish.** Replace
`Selection.destination` with provider-aware reference, give core a
single webhook-auth mixin, optional provenance logging.
Risk: low.

## Options considered

**Option A (chosen): explicit `connect.provider` registry + per-record
binding + façade dispatch.** Provider is a first-class entity.
Domain models are thin; provider modules implement methods on a
shared abstract class. Per-user provider binding is many-to-many
through a link model that itself is extensible per provider. Costs
schema work (new models, migration of user fields) but cleanly
supports N providers and per-record provenance.

**Option B: keep MRO dispatch, formalise it.** Add an `@abstractmethod`
decorator to core methods and a runtime check that exactly one
provider overrides each. Works today but breaks the moment two
providers want to coexist (back to "last wins"). Per-record
provider binding is also unaddressed. Rejected: it codifies the
current pain.

**Option C: per-provider Odoo databases.** Run two Odoo databases,
one per provider, federate via API. Clean separation, terrible UX
(no unified user list, no unified call log, license duplication).
Rejected: incompatible with the "single Odoo CRM enriched with
calls" product story.

**Option D: provider as a polymorphic mixin only.** Provider methods
live on the domain models as today, but each model gets a
`provider_id` Many2one and the override does
`if self.provider_id.code != 'twilio': return super()`. Less new
schema, but the dispatch logic is duplicated on every method and
each domain model still has to know about every provider's quirks.
Rejected: scales worse than Option A for ≥ 3 providers and leaves
no place to put `_get_webrtc_config()` (it has no owning record).

## Consequences

- **Adding a new provider is a self-contained module.** New
  `connect_<x>` module: declares a `connect.provider` record,
  inherits and implements provider methods, extends the binding
  model with its required per-user fields, registers its phone
  adapter. No core change needed.
- **Per-record provenance.** Reports like "Twilio call volume vs
  FreeSWITCH call volume" become trivial GROUP BYs on
  `connect.call.provider_id`. Today they require JOINing through
  Twilio-SID / FS-UUID fields.
- **Per-user multi-homing.** A receptionist with both a Twilio
  WebRTC widget in the browser *and* a FreeSWITCH desk phone
  registered to the same `connect.user` becomes a supported scenario,
  not a hack.
- **Settings UI scales linearly with provider count.** Each
  provider owns its own sub-config; the shared form is only
  general/transcription/anchor.
- **One frontend phone icon, regardless of provider count.**
- **Migration cost is non-trivial.** Phase 4 in particular requires
  per-record field migration on user data; it should be staged with
  dry-run + rollback. Each phase ships independently, so the risk
  is bounded per release.
- **`connect_elevenlabs` becomes a provider too** (not a special
  case). The existing per-agent SIP provisioning of ADR-021 fits
  naturally as a Phase-2 `provider_id` on `connect.call` whose
  `_render_callflow` returns the EL-specific bridge.
- **Existing ADRs (017–021) remain valid.** They describe the
  current single-provider-at-a-time flows. The new architecture
  generalises them; it does not contradict them.
- **Backwards compatibility window.** Phases 3 and 4 keep legacy
  override paths and field accessors for at least one minor release,
  so external customisations of these models keep working while we
  migrate.

## Open questions (defer to follow-up ADRs)

- Migration script details for Phase 4 → ADR-024.
- Whether `connect.callflow` should support *mixing* providers
  within a single flow (e.g., FS IVR that hands off to a Twilio SMS
  step) or whether flow → provider is 1:1. Punted; current consumers
  are 1:1, so start with 1:1 and revisit if needed.
- Whether per-provider settings configs should be singletons or
  multi-tenant (e.g., two Twilio accounts in one Odoo). Today they
  are singletons; the new sub-model already permits multiplicity at
  no extra cost, but UI for picking among multiple Twilio accounts
  is out of scope for this ADR.
- **Provider-specific actions on `connect.call` (parking, transfer,
  hold, mute, voicemail-drop).** Today
  `connect.call.action_fs_park()` and the `fs_parked_slot`
  computed field live on the core `connect.call` model and are
  exposed via a view-level button that is invisible when not
  applicable. This is technically a leak (a core model carries an
  FS-only action), but the alternative — introducing a generic
  `_call_park()` / `_call_transfer()` / `_call_hold()` capability
  system on `connect.provider` — would right now be an abstraction
  with exactly one implementer. Decision: **leave parking on core
  `connect.call` as-is**; revisit when (a) a Twilio parking use
  case appears, or (b) a 3rd provider with parking enters the
  picture. Same principle for transfer/hold/mute/voicemail-drop:
  abstract only when a second implementation forces the question.
  Likely follow-up: ADR-025 once a second implementer exists.
