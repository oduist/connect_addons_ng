# ADR-019: ElevenLabs SIP Trunk Configuration — Per-Agent + Tenant Defaults

**Status:** Superseded by ADR-020
**Date:** 2026-04-29
**Refines:** ADR-018

## Context

ADR-018 placed all SIP-trunk configuration on the singleton
`connect.settings` model. Real ElevenLabs deployments tie a SIP trunk
to a *phone number* and each phone number to *one agent*. Tenants
that operate multiple agents over a single shared trunk want to
configure credentials once; tenants that have one trunk per agent
want per-agent overrides. ADR-018's single-record model couldn't
express either case cleanly.

Additionally, SIP trunking is opt-in: tenants without SIP at all were
forced to fill in a username/password just to keep the settings page
saveable.

## Decision

Split the SIP-trunk configuration across `connect.settings`
(tenant defaults) and `connect.elevenlabs_agent` (routing + override).
Add explicit on/off toggles on both records.

### `connect.settings` — tenant defaults

| Field | Type | Notes |
|---|---|---|
| `elevenlabs_sip_enabled` | Boolean | default `False` |
| `elevenlabs_sip_auth_method` | Selection | `digest` / `acl`, default `digest` |
| `elevenlabs_sip_username` | Char | `groups="base.group_erp_manager"` |
| `display_elevenlabs_sip_username` | Char | mirror, masked |
| `elevenlabs_sip_password` | Char | `groups="base.group_erp_manager"` |
| `display_elevenlabs_sip_password` | Char | mirror, masked |

Routing fields (`inbound_addresses`, `outbound_addresses`,
`allowed_numbers`) — **removed** from settings; they belong on the
agent.

`elevenlabs_sync_sip_trunks()` raises `ValidationError` if the toggle
is off.

### `connect.elevenlabs_agent` — per-agent

| Field | Type | Notes |
|---|---|---|
| `sip_enabled` | Boolean | default `False` |
| `sip_inbound_addresses` | Char | CSV of SIP URIs / CIDRs |
| `sip_outbound_addresses` | Char | CSV of SIP URIs |
| `sip_allowed_numbers` | Char | CSV of E.164 |
| `sip_override_credentials` | Boolean | default `False` |
| `sip_username` | Char | plain — no display_* mirror |
| `sip_password` | Char | plain — `password="1"` on form input |

Helper `_resolve_sip_credentials()` returns the effective
`(username, password, auth_method)` triple:

* `auth_method` always taken from settings.
* `username`/`password`: agent's values when both `sip_enabled` and
  `sip_override_credentials` are true; otherwise fall back to the
  tenant defaults via `Settings.sudo().get_param(...)`.

Agent SIP creds are **not** wrapped in the `display_*`/
`PROTECTED_FIELDS` masking pattern — `connect.group_admin` already
gates agent edit access, and the rest of `connect.elevenlabs_agent`
does not store secrets that way (precedent: no existing field on the
agent uses `groups="base.group_erp_manager"`). Password input is
visually masked via `password="1"` on the form.

## Consequences

* Tenants without SIP can save the settings page untouched. Existing
  default flows (Twilio Media Streams, FreeSWITCH audio_fork) are
  unaffected.
* Tenants with one shared trunk fill the creds once on settings, flip
  `sip_enabled` per agent, leave `sip_override_credentials` off.
* Tenants with per-agent trunks turn on the override and supply
  per-agent credentials.
* Per-number provisioning (POST `/v1/convai/phone-numbers`) — still
  out of scope; the helper `_resolve_sip_credentials()` is what that
  follow-up will read from.

## Migration

No data migration required. ADR-018 fields landed on this branch
within a single dev session; the running Odoo never restarted to
materialise the routing-fields columns. `-u connect_elevenlabs`
creates the new schema in one shot.
