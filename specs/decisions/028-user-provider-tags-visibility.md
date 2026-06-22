# ADR-028: Editable provider tags on the user form + provider-driven field visibility

**Status:** Accepted
**Date:** 2026-06-22
**Builds on:** ADR-023 (multi-provider architecture), ADR-024 (user↔provider binding, Phase 4a)
**Tracked in:** Linear `ODU-40` (follow-up to `ODU-39`)

## Context

ADR-024 Phase 4a introduced `connect.user.provider.binding` and the
`connect.user.provider_ids` Many2many compute, but exposed them only as a
readonly badge plus an editable bindings list buried in a *Providers*
notebook page. ODU-39 removed the readonly duplicate. Two gaps remained:

1. There was no first-class, in-your-face way to pick a user's providers
   from the main form — you had to open a notebook tab and add binding
   rows.
2. Every provider-specific field cluster (Twilio `username`, `domain`,
   `twilio_edge`, `whatsapp_sender_id`, `application`, the *Phone* tab;
   FreeSWITCH *WebRTC* / *Endpoints* tabs and the Endpoints stat button)
   is rendered **unconditionally**, regardless of whether the user is
   actually on that provider. A pure-FS user still sees the whole Twilio
   cluster and vice-versa.

The desired UX: a `many2many_tags` widget in the main form to add/remove
providers, and provider-specific fields that appear only when their
provider tag is present.

This is *not* ADR-024 Phase 4b. Phase 4b moves the provider fields off
`connect.user` into provider-specific binding extensions, makes the
binding the single source of truth, and rewrites dispatch — a large,
high-risk change. This ADR delivers the UX with a bounded, additive
change and explicitly stops short of Phase 4b.

## Decision

### Scope (v1): membership + visibility only

- The provider tag drives **binding membership** and **field
  visibility**.
- Provider **behavior** (call origination, WebRTC bootstrap, the Twilio
  REST calls in `res.users` lifecycle) continues to key on its own
  legacy fields (`username`, `webrtc_enabled`, `sip_enabled`, …) exactly
  as today. No field move, no dispatch rewrite, no migration.

### Boundary

Core never references provider codes. Core owns the tags; each provider
module owns the visibility of its own fields.

**Core (`connect`)**
- `connect.user.provider_ids` becomes editable: keep the `compute` over
  `provider_binding_ids.provider_id`, add an `inverse` that creates /
  unlinks `connect.user.provider.binding` rows, drop `readonly=True`.
  Bindings stay the canonical store (ADR-024).
- Form: `provider_ids` rendered as `many2many_tags` with
  `{'no_create': True}` (providers are a module-managed registry; users
  don't invent them) in the *Call Settings* group.
- Remove the now-redundant *Providers* notebook page.

**`connect_twilio`**
- Computed boolean `is_twilio_enabled` =
  `'twilio' in provider_ids.mapped('code')`.
- Each of its form fields / the *Phone* tab carries
  `invisible="not is_twilio_enabled"`.

**`connect_freeswitch`**
- Computed boolean `is_freeswitch_enabled` (symmetric).
- *WebRTC* / *Endpoints* tabs and the Endpoints stat button carry
  `invisible="not is_freeswitch_enabled"`.

Both flags are non-stored computes depending on `provider_ids.code`, so
the form re-evaluates `invisible` live when the tag set changes, before
save.

## Consequences

- Providers are managed in one obvious place; the form shows only the
  fields relevant to the user's providers.
- No schema change → no migration. Only manifest version bumps
  (`connect`, `connect_twilio`, `connect_freeswitch`).
- **Known v1 limitation (accepted):** untagging a provider hides its
  fields but leaves the legacy data in the DB, and the provider may
  still function (its behavior keys on its own fields, not on the tag).
  Likewise, setting a legacy field programmatically (e.g. Twilio user
  provisioning via API) does not auto-create a binding/tag. Closing this
  gap means making the binding the single source of truth — ADR-024
  Phase 4b — deliberately deferred.

## Options considered

**A (chosen): editable tags via compute+inverse, per-provider visibility
flags.** Bounded, additive, respects the core boundary. Delivers the UX
without touching dispatch or migrating data.

**B: full ADR-024 Phase 4b now.** Move fields onto binding extensions,
binding as source of truth, rewrite dispatch. Correct end state but
large and high-risk; the UX value is available without it. Deferred.

**C: keep the bindings notebook list, skip tags.** Status quo after
ODU-39. Rejected — does not meet the "manage in the main interface"
goal and does nothing for field clutter.

## Rollback

Purely additive view + field changes. Revert the commit; the
`provider_ids` field returns to readonly-compute, the *Providers* page
returns, the visibility flags disappear. No data to undo.
