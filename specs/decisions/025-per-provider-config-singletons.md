# ADR-025: Per-provider configuration singletons (ADR-023 Phase 6, hybrid rollout)

**Status:** Accepted
**Date:** 2026-05-27
**Builds on:** ADR-023 (multi-provider architecture)
**First implementation:** ODU-11 (ElevenLabs)
**Follow-ups:** ODU-11b (Twilio), ODU-11c (FreeSWITCH)

## Context

ADR-023 Pillar 3 calls for per-provider configuration sub-models —
`connect.provider.<code>.config` — to replace the flat
`connect.settings` notebook that today carries every provider's settings
(Twilio +11 fields, FreeSWITCH +24, ElevenLabs +9). The fields are
declared by each provider module via `_inherit = 'connect.settings'`,
which forces every reader (settings form, controllers, `get_param`
callsites, sync jobs) to go through a single mega-model.

Doing this in one shot for all three providers is large and risky:
~45 callsites for Twilio, ~50 for FreeSWITCH, ~17 for EL, plus view
restructuring and migration of stored values for every install.

## Decision

Roll out Phase 6 **per provider**, starting with the smallest
(ElevenLabs, 9 fields, ~17 callsites). The pattern established for EL
becomes the template for Twilio and FreeSWITCH follow-ups.

### Per-provider pattern

For each provider `<code>`:

1. **New model** `connect.provider.<code>.config` in
   `connect_<code>/models/provider_config.py`:
   - Regular `models.Model` (not Transient).
   - Field names strip the `<code>_` prefix that they carried on
     `connect.settings`. E.g.
     `connect.settings.elevenlabs_api_key` → `connect.provider.elevenlabs.config.api_key`.
   - Singleton accessor: `@api.model def _get(self):` returns / creates
     the one row.
   - Protected-fields display-mask pattern is reimplemented on the new
     model (local `PROTECTED_FIELDS` set + `write()` override) — the
     pattern is generic but the new model needs its own copy of the
     logic because `connect.settings.write` doesn't see the new model.
   - All provider-specific methods that previously lived on
     `connect.settings` (e.g. `get_elevenlabs_client`,
     `_push_elevenlabs_initiation_webhook`, `elevenlabs_sync_*`) move
     here, with the prefix stripped.

2. **Migration** at the provider module's manifest version bump
   (e.g. `connect_elevenlabs/migrations/19.0.1.1.9/post-migrate.py`):
   - Insert the singleton row (with `agent_token` UUID generated in
     Python — raw INSERT skips ORM defaults).
   - Copy values from `connect_settings.<code>_*` to the new singleton's
     fields.
   - `ALTER TABLE connect_settings DROP COLUMN "<code>_..."` for every
     migrated column.
   - Raw SQL throughout — the columns are about to be removed, so
     reading them via the ORM is brittle.
   - Idempotent: gated on `information_schema.columns` checks.

3. **Callsites:** every
   `env['connect.settings'].sudo().get_param('<code>_X')`
   becomes
   `env['connect.provider.<code>.config'].sudo()._get().X`.
   Bulk replace via regex; review by hand.

4. **Settings model trim:** `connect_<code>/models/settings.py` keeps
   only fields that **aren't** provider-specific — e.g.
   `transcript_provider = fields.Selection(selection_add=[...])` is a
   core field with a `<code>` *option*, not a `<code>`-specific field,
   so it stays.

5. **View XML retarget:** the existing per-provider settings form (if
   it already exists as a standalone view, like EL's) flips its
   `<field name="model">connect.settings</field>` to the new model and
   drops the `<code>_` prefix from every `<field name>`.

6. **Server action retarget:** the menu action button's `model_id` ref
   points at the new model; the action code calls
   `model._get().action_open_form()`.

7. **Security:** add `ir.model.access` records for the new model
   (group_admin: full CRUD).

### Why "hybrid", not big-bang

EL is the smallest of the three. Twilio has more fields and more
callsites, and FS has the most plus the most complex settings UI
(currently embedded in the core settings notebook page, not a
standalone form). Going EL → Twilio → FS lets each round validate the
pattern on lower stakes before moving up.

The intermediate state is consistent: each provider's config either
lives in the new singleton (migrated) or still on `connect.settings`
(pending migration). No mixed state per provider.

## Options considered

**A (chosen): per-provider, smallest first.** EL → Twilio → FS.
Validates the pattern on the smallest surface. Each round is bounded.

**B: big-bang full Phase 6 across all three providers.** Matches the
original ADR-023 text. Rejected for risk; one bad migration on
upgrade breaks every settings-reading caller in the codebase.

**C: additive only (Phase 6a).** Add the new singletons as mirrors of
`connect.settings`, route new readers through them, never drop the old
fields. Rejected — the actual UI clutter problem doesn't go away
without removing fields from `connect.settings`.

## Consequences

- `connect.settings` shrinks per provider rollout.
- Each provider owns its config model in its own module — uninstalling
  the provider also uninstalls the config table.
- Callsite churn is unavoidable but mechanical (regex-bulkable, see
  ODU-11 commit for EL).
- The display-mask pattern duplication is one-time per provider; a
  mixin abstraction can be considered if a 4th provider arrives, but
  isn't justified for the current three.
- `connect.provider.config_model` (placeholder Char added in ODU-5) now
  has a meaning — each provider entry can carry the dotted name of its
  config model. Not used yet by core dispatch; available for future
  generalised `provider._config_record()` helper.

## Rollback

Per migration:
- `DROP TABLE connect_provider_<code>_config`
- Migration recreated `connect_settings.<code>_*` columns lost any
  values stored *after* the migration ran but before rollback. Real
  rollback strategy: don't roll back; instead fix forward by writing a
  reverse migration that re-adds columns and copies data back. Risk is
  low on the test environment (handful of rows) and bounded on prod
  by the per-provider scope.
