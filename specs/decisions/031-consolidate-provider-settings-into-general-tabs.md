# ADR-031: Consolidate Twilio + FreeSWITCH settings into General Settings tabs; nest provider menus under PBX

**Status:** Accepted
**Date:** 2026-06-25
**Linear:** ODU-46
**Partially reverses:** ADR-025 (per-provider config singletons) for Twilio + FreeSWITCH only; ADR-023 Pillar 7 (provider root menus as siblings of the app root).

## Problem

ADR-025 split each provider's settings off the flat `connect.settings`
notebook into dedicated singletons (`connect.provider.twilio.config`
ODU-22, `connect.provider.freeswitch.config` ODU-23), each with its own
standalone form opened from a per-provider **Settings** menu item. The
result is three separate places an admin configures the system
(Configuration → Settings, Twilio → Settings, FreeSWITCH → Settings),
and two extra top-level app menus (FreeSWITCH, Twilio) sitting as
siblings of the core menus.

The product owner wants the configuration unified again: one
**General Settings** form with a tab per installed provider, and the
provider feature menus nested under the existing **PBX** menu rather
than competing at the top level.

## Decision

Two coupled changes, shipped together on branch `19.0-twilio-fs-compat`:

### 1. Settings → back onto `connect.settings`

- Delete models `connect.provider.twilio.config` and
  `connect.provider.freeswitch.config`. Each provider module re-declares
  `class Settings(models.Model): _inherit = 'connect.settings'` and moves
  its fields **and** methods back (the pre-ODU-22/23 design).
- **Field names: restore the original prefixed schema** — exact inverse
  of the ODU-22/23 rename. `api_key → twilio_api_key`,
  `socket_url → freeswitch_socket_url`, etc.; `firewall_*` unchanged;
  the never-prefixed Twilio fields (`account_sid`, `auth_token`,
  `display_auth_token`, `fetch_call_prices`) keep their names. Rationale:
  these now live on a shared admin model, so prefixes prevent semantic
  collisions and keep the model self-documenting; it also makes the data
  migration a clean inverse of ODU-22/23.
- The two standalone forms, their `ir.actions.server`, and their
  per-provider **Settings** `menuitem`s are removed. Each provider adds a
  notebook page to `connect.connect_settings_form` via view inheritance,
  shown only when that module is installed. Each page contains a
  **nested notebook** preserving the current grouping: FreeSWITCH →
  *Server* / *Firewall*; Twilio → *API* / *Behavior*.
- A `_get()` singleton accessor is added to core `connect.settings` so
  the existing `…_get().<attr>` call style keeps working after the model
  merge.

### 2. Menu → provider roots under PBX

Reparent `connect_twilio.menu_connect_twilio` and
`connect_freeswitch.menu_connect_freeswitch` from `connect.menu_connect_root`
to `connect.menu_connect_pbx`. Their child menus follow by reference. The
provider root still owns its children (Pillar 7's ownership intent
preserved); only the nesting depth changes.

## Options considered

**A (chosen): full revert for Twilio + FS** — move fields+methods back,
restore prefixes, delete config models. Cleanest single-form UX; matches
the documented "each integration adds its own page via view inheritance"
pattern. Cost: ~110 mechanical call-site edits + a data migration.

**B: keep config models, mirror fields onto `connect.settings` as
`related` fields.** No migration, preserves ADR-025 separation. Rejected
by product owner — wanted the models merged, and `related`-field mirrors
of ~37 fields are their own boilerplate.

**C: keep standalone forms, only reparent menus.** Rejected — does not
deliver the "one settings form" goal.

## Field re-prefix mapping (inverse of ODU-22/23)

Twilio (`connect_provider_twilio_config` → `connect_settings`):

| config model | restored on connect.settings |
|---|---|
| account_sid | account_sid |
| auth_token | auth_token |
| display_auth_token | display_auth_token |
| api_key | twilio_api_key |
| api_secret | twilio_api_secret |
| display_api_secret | display_twilio_api_secret |
| balance | twilio_balance |
| region | twilio_region |
| edge | twilio_edge |
| auto_sync | twilio_auto_sync |
| verify_requests | twilio_verify_requests |
| fetch_call_prices | fetch_call_prices |

FreeSWITCH (`connect_provider_freeswitch_config` → `connect_settings`):

| config model | restored on connect.settings |
|---|---|
| socket_url | freeswitch_socket_url |
| domain | freeswitch_domain |
| ice_servers | freeswitch_ice_servers |
| log_level | freeswitch_log_level |
| sofia_log_level | freeswitch_sofia_log_level |
| xmlrpc_host | freeswitch_xmlrpc_host |
| xmlrpc_port | freeswitch_xmlrpc_port |
| xmlrpc_user | freeswitch_xmlrpc_user |
| xmlrpc_password | freeswitch_xmlrpc_password |
| status | freeswitch_status |
| uptime | freeswitch_uptime |
| active_calls | freeswitch_calls |
| registrations | freeswitch_registrations |
| gateway_statuses | freeswitch_gateway_statuses |
| firewall_* | firewall_* (unchanged) |

## Methods relocated onto `connect.settings` (via `_inherit`)

- Twilio: `_get` reuse, `get_client`, `sync`, `get_balance`,
  `_originate_call`, `compute_sip_uri`, `get_external_call_route`,
  `_reset_edge` onchange, protected-field `write()` for
  `display_auth_token` / `display_twilio_api_secret`.
- FreeSWITCH: `get_webrtc_config`, `freeswitch_api`, `check_status`,
  `_validate_firewall_secret`, protected-field `write()` for
  `display_firewall_service_token`, and the firewall-agent
  `_trigger_sync('settings')` on `firewall_*` change.

The FS back-compat shim methods in `connect_freeswitch/models/settings.py`
become the real implementations (no longer delegating to the config
model).

## Call-sites

`grep` count: ~80 Twilio + ~30 FS references of the form
`env['connect.provider.<p>.config'].sudo()._get().<attr>` /
`.get_client()` / `.sync()` / `.get_webrtc_config()` etc. Each becomes
`env['connect.settings'].sudo()._get().<prefixed-attr>` (field reads) or
`env['connect.settings'].sudo().<method>()` (methods). Regex-bulkable per
provider, reviewed by hand. Includes `connect_elevenlabs_twilio` and the
`connect/models/provider.py:18` config_model placeholder string.

## Data migration

New `post-migrate.py` under each provider's next manifest version,
inverse of the ODU-22/23 scripts:

1. For each restored column, `ALTER TABLE connect_settings ADD COLUMN IF
   NOT EXISTS …` (the ORM will also create them on upgrade; the explicit
   add keeps the copy step self-contained and idempotent).
2. Copy values from the config table's single row into the
   `connect_settings` singleton row using the inverse name map.
3. The `connect_provider_<p>_config` tables drop automatically when the
   models are removed on upgrade (Odoo ORM removes the table for a model
   that no longer exists). Raw SQL throughout; idempotent via
   `information_schema` checks.

## Security

- Remove the `ir.model.access` rows for both deleted config models.
- `connect.settings` stays **admin-only** — no `connect.group_user`
  access (CLAUDE.md rule; it holds API keys/tokens).

### WebRTC access (must-resolve)

`phone_service.js` RPC-calls `connect.settings.get_webrtc_config`, and
today FS grants `connect.group_user` *read* on the config model
specifically so a plain Connect User can reach it. Moving the method onto
admin-only `connect.settings` would break WebRTC for non-admins.

**Resolution (decide at implementation, do NOT widen connect.settings
ACL):** confirm the current non-admin path first, then route WebRTC
config through a user-accessible surface — preferred a JSON controller
(`/connect_freeswitch/webrtc_config`, sudo internally) or expose it on a
model the user already reads (e.g. `connect.user`). Update the JS caller
accordingly.

## Out of scope

`connect.provider.elevenlabs.config` (ODU-11) keeps the ADR-025 pattern —
not in this request. Accepted minor inconsistency: EL configures from its
own menu while Twilio/FS configure from General Settings tabs.

## Manifest / images

- Bump `connect_twilio` and `connect_freeswitch` manifest versions once
  each (one release unit), plus `connect` if core `_get()` lands there.
- No `connect_freeswitch/deploy/**` change → **no Docker image rebuild**.

## Implementation plan (ordered)

1. Core: add `_get()` to `connect.settings`.
2. `connect_twilio`: re-add fields (prefixed) + methods to
   `Settings(_inherit)`, delete `provider_config.py`, delete
   `settings_views.xml` form/action/Settings-menu, add inherited notebook
   page (nested API/Behavior) into `connect.connect_settings_form`,
   reparent `menu_connect_twilio` under PBX, drop config ACL, add
   migration, update ~80 call-sites.
3. `connect_freeswitch`: same shape (Server/Firewall nested page),
   resolve WebRTC access path, reparent `menu_connect_freeswitch` under
   PBX, drop config ACL (keep the WebRTC user path), add migration,
   update ~30 call-sites.
4. Update specs (`connect_core.md`, `connect_twilio.md`,
   architecture/settings notes) and docs (admin settings/menu pages).
5. Verify in an oduflow env: upgrade both modules, check migration moved
   values, both tabs render install-conditionally, menus nest under PBX,
   WebRTC still works for a non-admin user, Twilio sync/balance still
   work. Run `run_odoo_tests` for all three modules.

## Rollback

Fix-forward only (same posture as ADR-025). A reverse migration would
re-create the config tables and copy back; not anticipated.
