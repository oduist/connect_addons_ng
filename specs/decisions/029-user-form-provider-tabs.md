# ADR-029: Fence provider-specific user fields into named tabs

**Status:** Accepted
**Date:** 2026-06-22
**Builds on:** ADR-023 (Pillar 7 — provider-owned UI sections), ADR-028
(provider tags + visibility flags)
**Tracked in:** Linear `ODU-41` (follow-up to `ODU-40`)

## Context

After ODU-39/ODU-40 the `connect.user` form lets you pick providers via
tags and hides a provider's fields when its tag is absent. But when a
user is on more than one provider the fields are still **mixed**:

- Twilio fields are scattered across the shared *User Info* group
  (`username`, `domain`, `twilio_edge`) and *Call Settings* group
  (`whatsapp_sender_id`, `application`), interleaved with
  provider-agnostic fields, with no "this is Twilio" label.
- FreeSWITCH fields live in their own *WebRTC* / *Endpoints* tabs, but
  the tab names don't say "FreeSWITCH".

There is nothing telling the admin which field belongs to which stack.

Settings (`connect.settings`) is already clean — Twilio and FreeSWITCH
config moved to dedicated `connect.provider.<code>.config` forms under
their own root menus (ADR-025 / ODU-22). This ADR brings the same
"provider-owned section" clarity (ADR-023 Pillar 7) to the user form.

## Decision

Each provider's fields move into a **single notebook tab named after the
provider**, shown only when the user is bound to it (reusing the
`is_twilio_enabled` / `is_freeswitch_enabled` computes from ADR-028).
Shared groups keep only provider-agnostic fields.

Resulting tabs: `[Organization] [Twilio] [FreeSWITCH]` — the general
Organization tab leads, provider tabs follow.

**`connect_twilio`** — *Twilio* tab:
- Account: `username`, `domain`, `twilio_edge`
- Messaging: `whatsapp_sender_id`, `application`
- SIP Phone / Web Phone groups (the former standalone *Phone* tab)

Removes the xpath insertions into *User Info* / *Call Settings* and the
separate *Phone* page; the tab is inserted after the *Organization*
page. `is_twilio_enabled` stays as a hidden field anchored after
`provider_ids` (outside the conditionally-hidden tab, so
the tab's `invisible` modifier can read it). Per-field `invisible` flags
collapse into the single page `invisible`; only intra-field modifiers
(`password` hidden when `sip_enabled == False`, etc.) remain.

**`connect_freeswitch`** — *FreeSWITCH* tab:
- WebRTC group (`webrtc_enabled`, `originate_ring`, `phone_display_mode`)
- Endpoints list (`endpoint_ids`)

Merges the former *WebRTC* + *Endpoints* tabs into one. The Endpoints
stat button and `is_freeswitch_enabled` hidden field stay.

**Boundary:** core (`connect`) is untouched and stays provider-agnostic;
each provider module fences its own fields into its own tab.

## Consequences

- Each provider's settings are in one obvious, labelled place; shared
  groups carry only agnostic fields.
- View-only change in the two provider modules; core unchanged. No
  schema change, no migration. Version bumps for `connect_twilio` and
  `connect_freeswitch` only.
- Consistent with the already-separated provider Settings forms and with
  ADR-023 Pillar 7.

## Options considered

**A (chosen): one named tab per provider.** Maximum clarity, consistent,
reuses the visibility flags, respects the core boundary.

**B: labelled sub-groups inline in User Info / Call Settings.** Keeps
fields on the main page but fences each provider in a titled sub-group.
Rejected — Twilio fragments into multiple sub-groups across two groups
while FS stays in tabs; inconsistent and busier.

## Rollback

Purely additive/structural view changes. Revert the commits; the form
returns to the ODU-40 layout. No data to undo.
