# ADR-018: ElevenLabs SIP Trunk Provisioning via API

**Status:** Accepted
**Date:** 2026-04-29

## Context

ElevenLabs Conversational AI exposes SIP trunking as a first-class
phone-number provider (`POST /v1/convai/phone-numbers` with
`provider="sip_trunk"`, see EL docs changelog 2025-07-07). Two kinds
of configuration are involved:

1. **Trunk-level credentials and ACL** — username/password for SIP
   Digest authentication, allowed SIP URIs/IP ranges for inbound,
   destination addresses for outbound, optional E.164 whitelist of
   allowed callers.
2. **Per-number provisioning** — POSTing each E.164 number to
   ElevenLabs together with `inbound_trunk` / `outbound_trunk`
   payloads.

Both ADR-015 (FreeSWITCH SIP-trunk transport) and ADR-017 (Twilio
SIP-bridge transport) assume that an ElevenLabs SIP trunk already
exists for the tenant. Until now, that trunk had to be provisioned by
hand in the ElevenLabs dashboard. This is fragile (no record of the
config inside Odoo) and tedious for tenants that operate several
numbers.

## Decision

Capture the trunk-level config inside `connect.settings` and expose it
through a new **SIP Trunk** notebook page in the existing ElevenLabs
settings form (`connect_elevenlabs.connect_elevenlabs_settings_form`).

Per-number provisioning is **out of scope** for this ADR. It will be
addressed in a follow-up that touches `connect.number` and adds a
Provision button on the number form.

### Authentication

`elevenlabs_sip_auth_method` Selection — `digest` (default) or `acl`.

* `digest` — username + password are required; ElevenLabs sends them
  on every INVITE. Recommended by ElevenLabs because it survives
  ElevenLabs egress IP changes.
* `acl` — ElevenLabs egress IPs must be allow-listed on the SIP-trunk
  side. Username/password fields become optional. Adopting this mode
  means manually maintaining the IP allow-list, which is brittle —
  hence not the default.

### Stored fields (on `connect.settings`)

| Field | Type | Notes |
|---|---|---|
| `elevenlabs_sip_auth_method` | Selection | `digest` / `acl`, default `digest` |
| `elevenlabs_sip_username` | Char | `groups="base.group_erp_manager"` |
| `display_elevenlabs_sip_username` | Char | mirror; appended to `PROTECTED_FIELDS` |
| `elevenlabs_sip_password` | Char | `groups="base.group_erp_manager"` |
| `display_elevenlabs_sip_password` | Char | mirror, masked |
| `elevenlabs_sip_inbound_addresses` | Char | CSV of SIP URIs / CIDRs |
| `elevenlabs_sip_outbound_addresses` | Char | CSV of SIP URIs |
| `elevenlabs_sip_allowed_numbers` | Char | CSV of E.164 |

### Sync action

`elevenlabs_sync_sip_trunks()` — minimal first iteration:

1. Validate that an ElevenLabs API key is set (`get_elevenlabs_client`
   already raises if missing).
2. Validate that, when `auth_method == 'digest'`, both username and
   password are present.
3. Issue `GET https://api.elevenlabs.io/v1/convai/phone-numbers` with
   `xi-api-key` and surface the count of currently provisioned numbers
   via `connect_notify`.

The button is intentionally read-only at this stage. Actual
provisioning happens per number, in the follow-up ADR.

## Consequences

* Tenants get a stable place inside Odoo to record SIP trunk
  credentials. ADR-015 and ADR-017 SIP-bridge flows can read the same
  fields rather than hard-coding values.
* No automatic mutation of the EL side from this ADR — only read +
  validate. That keeps the blast radius low while we refine the
  data model before per-number provisioning lands.
* `PROTECTED_FIELDS` masking pattern is reused, so SIP credentials
  are hidden from non-managers, consistent with `elevenlabs_api_key`
  and `elevenlabs_post_call_webhook_secret`.

## Out of scope / next steps

* Per-number provisioning (`POST /v1/convai/phone-numbers`) on
  `connect.number`.
* Two-way reconciliation — pulling EL-side trunk state and reflecting
  drift back into Odoo.
* Multiple trunks per tenant — current model stores one trunk;
  multi-trunk would require a dedicated `connect.elevenlabs.sip_trunk`
  model and a new submenu under `elevenlabs_menu`.
