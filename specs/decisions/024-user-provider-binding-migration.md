# ADR-024: User ↔ provider binding (Phase 4a additive)

**Status:** Accepted
**Date:** 2026-05-27
**Builds on:** ADR-023 (multi-provider architecture)
**Tracked in:** Linear `ODU-7` (Phase 4a), follow-up to be opened as `ODU-7b`/`ODU-2x` (Phase 4b)

## Context

ADR-023 Pillar 2 introduces a per-user-per-provider link model
(`connect.user.provider.binding`) so a single `connect.user` can be
reachable on multiple telephony stacks at once — e.g. a receptionist
with both a Twilio Voice JS browser widget *and* a FreeSWITCH desk
phone registered to the same Odoo user.

Today the schema is flat: `connect.user` carries Twilio-specific fields
(`username`, `domain`, `twilio_edge`, `sip_priority`,
`client_priority`, `sip_ring_timeout`, `client_ring_timeout`) declared
by `connect_twilio` via `_inherit`, and FS-specific fields
(`webrtc_enabled`, `webrtc_password`, `originate_ring`,
`phone_display_mode`) declared by `connect_freeswitch`. ODU-1 (Phase 1)
dropped `required=True` from the Twilio fields so users with no Twilio
presence are legal. So multi-homing **already works in practice** — the
data is just spread across two coexisting field clusters on the same
row.

ADR-023 Phase 4 wants to:

1. Introduce a link model (`connect.user.provider.binding`).
2. Move Twilio/FS fields off `connect.user` into provider-specific
   extensions of the binding model.
3. Drop the legacy fields from `connect.user`.
4. Add `@api.depends('provider_binding_ids')` shims so external
   integrations reading `user.username` etc. don't break in the
   transition cycle.

(2)–(4) together are the **largest, riskiest change** in the entire
multi-provider refactor: every callsite reading `user.username` /
`user.webrtc_password` (~18 in-tree, unknown number of downstream
customisations) has to read from the new binding. The shim with
`search()` support, the migration to populate binding extensions, the
view-XML rewrites — all of it has to land in one tightly-coordinated
release.

## Decision

Split Phase 4 into **4a (this ADR)** and **4b (deferred)**.

### Phase 4a — additive (this work)

Introduce the binding model and the `provider_ids` Many2many compute on
`connect.user`, populate from existing field clusters, **leave the
legacy fields alone.**

- New core model `connect.user.provider.binding`:
  - `user_id` Many2one → `connect.user`, `ondelete='cascade'`, indexed
  - `provider_id` Many2one → `connect.provider`, `ondelete='cascade'`,
    indexed
  - `config` Json — placeholder for ADR-023 Phase 6 per-(user,provider)
    config bag
  - `UNIQUE(user_id, provider_id)` via `models.Constraint`

- `connect.user.provider_binding_ids` One2many.
- `connect.user.provider_ids` Many2many compute over
  `provider_binding_ids.provider_id`, stored, readonly.
- Form view exposes `provider_ids` as a readonly badge widget and adds
  a notebook page listing the bindings for inspection/editing by
  admins.

- post-migration backfill at `connect 19.0.3.1.8`:
  - User row with `username NOT NULL` → create binding to `twilio`.
  - User row with `webrtc_enabled = TRUE` → create binding to
    `freeswitch`.
  - Idempotent (gated on the unique constraint + `search_count` lookup).
  - No-op for ElevenLabs today (no per-user fields).

- New callsites (ADR-023 Phase 5 frontend adapters, Phase 6 settings
  selection) read from `user.provider_ids`. Legacy code keeps reading
  `user.username` / `user.webrtc_password` unchanged.

### Phase 4b — destructive (deferred to a separate ticket)

Open a follow-up ticket when one of these triggers fires:

1. A third provider needs its own per-user fields (the cluster of
   per-provider fields on `connect.user` becomes unmanageable).
2. Multiple Twilio accounts in one Odoo (the singleton assumption built
   into `connect.user.username` breaks).
3. External integration explicitly requests removal of the legacy
   surface.

Until then, the cost of Phase 4b (migrate fields, write compute+inverse
shims with `search()` support, fix every internal callsite, deal with
downstream customisations) is not justified.

The follow-up ticket will:

- Add provider-specific extensions to `connect.user.provider.binding`
  (e.g. Twilio-side fields `twilio_username`, `twilio_domain_id`, …).
- Write data into the extensions, then drop the columns from
  `connect_user`.
- Add computed-with-inverse shims on `connect.user` for the dropped
  fields, with `_search` implementations so existing
  `search([('username', '=', ...)])` calls keep working.
- Update views to point at the binding extensions instead of the
  shimmed fields.

## Options considered

**A (chosen): split 4a/4b.** Ship the link model + compute now, defer
the destructive part. Architecture progresses; risk is bounded to a new
table and a non-stored compute.

**B: full Phase 4 in one go.** Matches the original ADR-023 text.
Rejected for this iteration — the value of the destructive part is
mostly aesthetic until a triggering condition (above) appears, while
the risk to existing FS+Twilio coexistence (just stabilised through
ODU-1 … ODU-6) is real.

**C: defer Phase 4 entirely.** Skip the link model too. Rejected —
ADR-023 Phase 5/6 read from `user.provider_ids`; without 4a they have
nowhere to source it.

## Consequences

- `connect.user.provider.binding` becomes the canonical "which
  providers does this user use" answer.
- `user.provider_ids` is available for Phase 5 / Phase 6 to read.
- Backfill on upgrade creates the binding rows automatically; manual
  re-binding is supported through the user form's notebook page.
- No callsite changes today. No downstream-customisation risk.
- Legacy field clusters on `connect.user` remain a known short-term
  inconsistency; the follow-up ticket above is the cleanup path.
- `config` Json field on the binding stays unused until Phase 6 needs
  it (ODU-11). Added now so Phase 6 doesn't have to touch the binding
  schema.

## Rollback

Phase 4a's migration is purely additive: a new table and INSERTs into
it. If the deployment goes wrong, `DROP TABLE
connect_user_provider_binding` + `ALTER TABLE connect_user DROP COLUMN
provider_ids` (the stored compute column) returns to the pre-upgrade
state. No tooling beyond the bare SQL is justified for a backfill that
touches the same number of rows as `SELECT COUNT(*) FROM connect_user`
(2 rows on the test environment; small on real deployments).
