# Connect FreeSWITCH Module Specification

## Module Info

- **Name:** Oduist Connect FreeSWITCH
- **Technical:** `connect_freeswitch`
- **Version:** 19.0.2.0.0
- **Depends:** `connect`, `web`
- **Application:** False
- **License:** Proprietary

## Overview

The `connect_freeswitch` module extends the core `connect` module with
FreeSWITCH-specific functionality. The shared ledger models
(`connect.call`, `connect.user`, `connect.settings`) are extended via
`_inherit`; since ADR-031 the module also **owns its PBX configuration
models** as independent `connect.freeswitch.*` models (exten, callflow,
number, endpoint, outgoing caller ID) — no core counterparts exist. The
exten dst-Reference mechanics, the callflow language list and the E.164
caller-ID constraint are deliberate copies of the Twilio counterparts —
**no shared mixin**; fixes must be applied in both modules.

It ships **three deliverables**:

1. The Odoo addon proper — models, views, controllers under
   `connect_freeswitch/`.
2. A custom FreeSWITCH Docker image (`oduist/freeswitch`) under
   `deploy/`, used as the SIP backend.
3. A standalone SIP-firewall service (`oduist/freeswitch-firewall`)
   under `deploy/firewall/`, paired with the Odoo module and the FS
   image — see the dedicated section below.

Major features:
- WebRTC via FreeSWITCH `mod_verto` with a phone widget in the Odoo UI;
- XML-curl directory + dialplan generation driven by Odoo records;
- mod_fifo-backed call queues with static dialplan consumers (ADR-013);
- call parking with BLF subscriptions (ADR-012);
- gateway / outgoing route management;
- piper TTS module embedded in the image;
- SIP brute-force firewall integration (see below, ADR-014).

---

## Models

### settings.py — `_inherit = "connect.settings"`

Adds FreeSWITCH-side configuration plus the firewall settings. Key
firewall-related fields:

| Field | Type | Notes |
|---|---|---|
| `firewall_enabled` | Boolean | master toggle |
| `firewall_service_url` | Char | base URL of the firewall service container |
| `firewall_service_token` / `display_firewall_service_token` | Char | shared Bearer secret used in **both** directions (Odoo → `/firewall/sync` on the service and service → `/freeswitch/firewall/api/*` on Odoo). Masked; admin-only; validator requires ≥24 chars urlsafe. |
| `firewall_heartbeat_interval` | Integer | seconds, default 60 |
| `firewall_event_retention_days` | Integer | how long the audit log is kept; default 30 |
| `firewall_tcp_ports`, `firewall_udp_ports` | Char | comma-separated ports protected by the iptables chain |
| `firewall_banned_timeout` | Integer | auto-ban TTL (24 h default) |
| `firewall_authenticated_timeout` | Integer | trust TTL after a successful registration (7 days, sliding) |
| `firewall_expire_short_timeout` | Integer | challenge-response window (30 s) |
| `firewall_expire_long_timeout` | Integer | default-deny TTL after a challenge is sent but not answered (24 h) |
| `freeswitch_webhook_token` / `display_freeswitch_webhook_token` | Char | shared secret authenticating every FreeSWITCH → Odoo HTTP call (`/freeswitch/xml`, `/freeswitch/webhook/*`). Masked; admin-only; auto-generated (`secrets.token_urlsafe(32)`) by the field default, `post_init_hook` and the 19.0.1.10.6 migration (`ensure_webhook_token`). Paired with the container via the `FS_WEBHOOK_TOKEN` env var. See ADR-025 |

`write()` is extended to:
* validate the Firewall Service Token and the FreeSWITCH Webhook Token
  (length + character set) when an admin edits them in the UI;
* schedule a `/firewall/sync` POST via `cr.postcommit` whenever any
  `firewall_*` field changes.

`get_recording_webhook_url()` builds the recording upload URL
(`<web.base.url>/freeswitch/webhook/recording/<token>`) used by the
dialplan generators; it returns `''` (recording disabled) when the base
URL or the token is missing.

XML-RPC connectivity to FreeSWITCH (ADR-004, ADR-027, ADR-030):
* `_freeswitch_rpc(command, args)` — low-level `mod_xml_rpc` call
  returning a `(result, error)` tuple. `error` is `None` on success or
  one of `NOT CONFIGURED` / `UNREACHABLE` / `AUTH FAILED` /
  `INVALID RESPONSE`. The connection is **always HTTPS**
  (`https://<host>:<port>/RPC2`): `mod_xml_rpc` has no native TLS, so
  Traefik terminates HTTPS in front of it and proxies to the fixed
  internal port `8080`. The `freeswitch_xmlrpc_port` setting is the
  **public** Traefik port (default `443`); the internal port lives in
  the `FS_XMLRPC_INTERNAL_PORT` controller constant. The
  `freeswitch_xmlrpc_tls_verify` Boolean (default on) controls TLS
  certificate verification — turn it off only behind a self-signed dev
  certificate (ADR-030).
* `freeswitch_api(command, args)` — thin wrapper returning the response
  string or `False`; used wherever only success/failure matters.
* `check_freeswitch_status()` — backs the **CHECK STATUS** button;
  writes the specific failure reason into the read-only
  `freeswitch_status` field so admins can tell the failure modes apart.

### firewall.py — firewall models

| Model | Purpose |
|---|---|
| `connect.firewall.whitelist` | static IP / CIDR records that bypass all banning logic |
| `connect.firewall.blacklist` | static IP / CIDR records that are always blocked (manual permanent bans) |
| `connect.firewall.event` | audit log of every security-relevant event reported by the service |
| `connect.firewall.agent` | singleton holding service heartbeat data; backing model for the `/freeswitch/firewall/api/*` controllers the service calls |

**Whitelist / Blacklist** share the same shape (`name`, `ip_or_cidr`,
`active`, `note`). Both IPv4 and IPv6 are accepted; `create` / `write`
canonicalize the value via `_normalize_ip_or_cidr()` (compressed
lowercase IPv6, `/32`–`/128` stripped from host entries, network
address for CIDRs, IPv4-mapped IPv6 unwrapped — the same spelling
`ipset` uses, see ADR-037). `@api.constrains` validates the address
and enforces uniqueness per table on normalized values. Each
`create` / `write` / `unlink` schedules `connect.firewall.agent._trigger_sync()`.

**Event** is read-only from the UI (`create=false edit=false`) — it is
populated only by the service via the `/freeswitch/firewall/api/event`
controller. The `event_type` Selection covers: `auth_success`, `auth_fail`, `auto_ban`,
`manual_ban_applied`, `manual_unban_applied`, `whitelist_changed`,
`blacklist_changed`, `settings_changed`, `service_started`,
`service_error`. The `is_banned` computed flag, evaluated by polling
the service's live `/firewall/api/bans`, drives the Unban button.

**Agent (singleton)** holds `last_seen`, `version`, `esl_connected`,
`bans_count`, `authenticated_count`, `uptime_seconds` and a `status`
Selection (`online` / `stale` / `offline`) computed from `last_seen`
against `firewall_heartbeat_interval`.

`connect.firewall.agent` backs the **HTTP controllers under
`/freeswitch/firewall/api/*`** that the service calls (see
`controllers/firewall_api.py`). Each request must carry
`Authorization: Bearer <firewall_service_token>`; the controller
runs `sudo()` after the token check.

| Method | Route | Direction | Purpose |
|---|---|---|---|
| `fetch_config()` | `GET /freeswitch/firewall/api/config` | service → Odoo | returns `firewall_*` settings (without `firewall_service_token`) |
| `fetch_whitelist()` | `GET /freeswitch/firewall/api/whitelist` | service → Odoo | active whitelist records (`ip_or_cidr`, `name`, `note`) |
| `fetch_blacklist()` | `GET /freeswitch/firewall/api/blacklist` | service → Odoo | active blacklist records |
| `report_event(payload)` | `POST /freeswitch/firewall/api/event` | service → Odoo | create one `connect.firewall.event` |
| `report_heartbeat(payload)` | `POST /freeswitch/firewall/api/heartbeat` | service → Odoo | updates the agent singleton |
| `report_applied(ip, action, status="ok", message=None)` | `POST /freeswitch/firewall/api/applied` | service → Odoo | updates `last_sync_at` and sends a bus notification to admins |
| `_trigger_sync(scope="all")` | — | Odoo (internal) | schedules a Bearer-authenticated POST to `<firewall_service_url>/firewall/sync` via `cr.postcommit` |
| `_call_service_unban(ip)` | — | Odoo (internal) | DELETE `/firewall/api/bans/<ip>` and log a `manual_unban_applied` event |
| `_fetch_live_banned_ips()` | — | Odoo (internal) | GET `/firewall/api/bans` to drive `connect.firewall.event.is_banned` |
| `_cron_reconcile()` | — | ir.cron | every 5 min, calls `_trigger_sync("all")` as a safety net |

### Other models

Beyond firewall, the module contains:

| Model | Purpose |
|---|---|
| `connect.channel` (`_inherit`) | adds FreeSWITCH runtime softphone recording control handlers on the shared channel RPC surface. Verto active calls are controlled by live UUID because channel rows are created from CDR after hangup; ownership and state are read/written through FreeSWITCH channel variables. |
| `connect.user` (`_inherit`) | adds `freeswitch_exten` / `freeswitch_exten_number` (registered in `_pbx_number_fields()`), `freeswitch_outgoing_callerid`, `freeswitch_endpoint_ids`, WebRTC fields and dial-string generation; `originate_provider` `selection_add` `'freeswitch'`; the user-bridge voicemail prompt is spoken by Piper with `voicemail_lang = connect.user.language` (ADR-037) |
| `connect.freeswitch.endpoint` (own model, ADR-031) | SIP endpoint management (formerly `connect.endpoint`). `auth_password` is auto-generated as a typeable passphrase (`models/passphrase.py`, `secrets`-based), `readonly` + `copy=False`, defaulted on create; `action_regenerate_auth_password()` issues a new one. Empty passwords on existing endpoints are backfilled non-destructively by `backfill_endpoint_passwords(env)` (post-migration). UI uses the `endpoint_password` OWL widget (mask + Show/Hide + Copy) — see ADR-022 |
| `connect.freeswitch.exten` (own model, ADR-031) | extension routing (formerly `connect.exten`); dst Reference → `connect.user` / `connect.freeswitch.callflow` / `connect.freeswitch.endpoint` / `connect.fs_fifo` |
| `connect.freeswitch.callflow` + `_choice` (own models, ADR-031) | IVR configuration and FreeSWITCH destinations (formerly `connect.callflow`); `_get_piper_language()` returns the BCP-47 code used as the Piper TTS model key (must match a `<model language="...">` entry in `piper_tts.conf.xml`) |
| `connect.freeswitch.number` (own model, ADR-031) | DID assignment (formerly `connect.number`) |
| `connect.freeswitch.outgoing_callerid` (own model, ADR-031) | outbound caller IDs (formerly `connect.outgoing_callerid`); E.164 `+` constraint, single default |
| `connect.freeswitch.gateway` | SIP gateway records, rendered into pjsip_wizard XML |
| `connect.freeswitch.outgoing_route` | outbound routing rules |
| `connect.freeswitch.template` | Jinja2 templates for dialplan / directory XML |
| `connect.fs_fifo` | mod_fifo queue records (ADR-013); user agents list resolves via `freeswitch_exten_number` |
| `connect.freeswitch.parking.slot` | call parking (ADR-012) |

### Outbound Caller ID resolution

The number presented to the called party on an outbound PSTN call is
resolved from `connect.freeswitch.outgoing_callerid` in a fixed order:

**per-user `connect.user.freeswitch_outgoing_callerid` → system default (`is_default=True`) → extension**

Two origination paths apply it independently:

| Path | Where | Mechanism |
|---|---|---|
| Click-to-call from Odoo | `models/call.py` → `originate_call()` | b-leg `origination_caller_id_number` (ADR-027) |
| Desk phone / Verto → PSTN | `models/outgoing_route.py` → `generate_dialplan()` | `effective_caller_id_number` override in the `dialplan_outgoing_route` template, keyed off the `odoo_connect_user_id` channel variable (ADR-021, ADR-027) |

Only the number is pushed outwards; the outbound caller-id **name** is
blanked so the internal caller's name never reaches the PSTN (ADR-026).

The override lives only on the outbound leg, so internal
extension-to-extension calls keep showing the extension. When neither a
per-user nor a default CallerID is configured, the extension number is
used. This mirrors the Twilio integration (`connect_twilio/models/domain.py`).

---

## Security

The firewall service does not log into Odoo as any user. Instead, it
calls the `/freeswitch/firewall/api/*` HTTP controllers with
`Authorization: Bearer <firewall_service_token>`; the controllers run
`sudo()` after the token check passes. The same shared token also
authenticates Odoo → service calls (`/firewall/sync`,
`/firewall/api/bans/<ip>`).

The token (`connect.settings.firewall_service_token` / its display
twin) is bootstrapped on install / upgrade by `setup_firewall(env)` in
`connect_freeswitch/__init__.py` and validated on admin edits
(≥24 chars, `[A-Za-z0-9_-]` only).

### FreeSWITCH → Odoo endpoint authentication (ADR-025)

All HTTP endpoints FreeSWITCH calls on Odoo are `auth='none'` routes
guarded by `controllers/token_auth.py::check_fs_webhook_auth()`, which
compares the shared `freeswitch_webhook_token` with
`secrets.compare_digest` and **fails closed** (empty token ⇒ 401):

| Route | Caller | Token transport |
|---|---|---|
| `POST /freeswitch/xml` | mod_xml_curl | Basic auth (`gateway-credentials`) |
| `POST /freeswitch/webhook/cdr` | mod_xml_cdr | Basic auth (`cred`) |
| `GET/POST /freeswitch/webhook/parking` | dialplan `curl` app | `token` query param (Odoo renders the URL) |
| `PUT/POST /freeswitch/webhook/recording/<token>/<filename>` | `record_session` | path segment (a query string after `.wav` would break format detection) |

Recording uploads are additionally capped at 256 MB.

The FreeSWITCH container receives the token via the `FS_WEBHOOK_TOKEN`
env var (`vars.xml` → `$${webhook_token}` in `xml_curl.conf.xml` /
`xml_cdr.conf.xml`); the entrypoint warns loudly when it is unset.

### Access rules

See `security/access_rules.xml`.

Firewall models are **admin-only** — `connect_user` has no access at all (the
`Firewall` menu is also gated on `connect.group_admin`).

| Model | `connect_admin` | `connect_user` |
|---|---|---|
| `connect.firewall.whitelist` | CRUD | — |
| `connect.firewall.blacklist` | CRUD | — |
| `connect.firewall.event` | read + unlink | — |
| `connect.firewall.agent` | read + write | — |

Whitelist / blacklist edits are admin-only via the Odoo UI; the
service has no model-level access at all because it goes through the
sudoed controller.

### WebRTC password lifecycle (ADR-026)

Each WebRTC-enabled `connect.user` holds a `webrtc_password` used to
authenticate the Verto softphone against `mod_verto`. It is **rotated on
every credential issuance**: `connect.user._rotate_webrtc_password()`
(`models/fs_user.py`) generates a fresh `secrets.token_urlsafe(16)`,
stores it, and returns it. The rotation fires inside
`connect.settings.get_webrtc_config` (and the legacy duplicate route
`/connect/webrtc/config`), i.e. roughly once per softphone boot / page
load. A leaked password therefore self-invalidates the next time the
user's softphone fetches its config.

FreeSWITCH re-authenticates every Verto registration live against the DB
value through the `/freeswitch/xml` directory binding, so a rotation
takes effect immediately — no FS reload or `xml_locate` flush.

To keep multiple browser tabs of the same user in sync, the helper also
pushes the new `{login, password}` to the user's **private** bus channel
(`self.user.partner_id`, notification type
`connect_freeswitch.verto_credentials`); `phone_service.js` updates the
live `VertoClient` password in place (`updateCredentials`). Active calls
are not interrupted. The password is never surfaced in any view.

### Softphone recording controls

The Verto phone widget exposes a recording toggle while a call is active. It
calls the core `connect.channel` softphone recording RPCs with provider
`freeswitch` and the live Verto UUID. The provider handler:

* checks access from live FreeSWITCH variables (`odoo_user_id`,
  `odoo_connect_user_id`, `odoo_caller_pbx_user_id`, `odoo_called_user_id`);
* starts manual segments with `uuid_record <uuid> start <upload-url>/<uuid>__<segment>.wav`;
* stops the active manual segment from `odoo_recording_path`, or the default
  `record_session` path only when the live UUID carries an
  `execute_on_answer=record_session ...` variable;
* stores `odoo_recording_state`, `odoo_recording_ref`,
  `odoo_recording_path` and `odoo_recording_error` on the live UUID.

User-level `record_calls=True` is not enough to infer an active recording by
itself, because Odoo-originated click-to-call legs do not start
`record_session`. Failed start/stop attempts reset the live state out of
`starting` / `stopping` so the softphone can retry.

---

## Crons (`data/ir_cron.xml`)

| Name | Code | Interval |
|---|---|---|
| `Firewall: reconcile state with the service` | `model._cron_reconcile()` | 5 minutes |
| `Firewall: delete old security events` | `model._cron_cleanup()` | daily |

The reconcile cron is the safety net for missed postcommit POSTs;
event cleanup keeps the audit log within `firewall_event_retention_days`.

---

## Views

`views/firewall_views.xml`:
* tree + form for whitelist and blacklist (admins only);
* read-only tree + form for events, plus a search view with quick
  filters by event type and group-by IP;
* a singleton form for the agent record with status badge;
* the Unban button on auto_ban events (visible only when the IP is
  still in the live banned set);
* a `FreeSWITCH → Firewall` menu structure with sub-items
  `Agent Status`, `Whitelist`, `Blacklist`, `Events`.

`views/settings.xml`:
* **standalone** FreeSWITCH settings form (XML-RPC connection, domain,
  webhook token, recording upload, plus the `Firewall` page — Enabled
  toggle, Service URL, masked Firewall Service Token, heartbeat interval,
  retention, ports, timeouts), opened through the core parametrized
  `open_settings_form()`; no notebook pages are injected into the core
  settings form (ADR-031).

### Menu structure

`connect_freeswitch` owns the **FreeSWITCH** submenu of the Connect app
(ADR-031). All provider submenus share sequence 50 under
`connect.menu_connect_root`, so they appear after Calls/Users in installation
order and before the core Configuration menu (seq 100).

```
Connect > FreeSWITCH (seq 50)
  +-- Numbers (seq 10)
  +-- Extensions (seq 20)
  +-- Call Flows (seq 30)
  +-- Endpoints (seq 40)
  +-- Outgoing Caller IDs (seq 50)
  +-- FIFO Queues (seq 60)
  +-- Parking Slots (seq 70)
  +-- Firewall (seq 80, admin)
  |   +-- Agent Status / Whitelist / Blacklist / Events
  +-- Configuration (seq 100, admin)
      +-- SIP Gateways
      +-- Outgoing Routes
      +-- XML Templates
      +-- Settings
```

---

## Migration (19.0.2.0.0, ADR-031)

Production runs FreeSWITCH only, so `connect_freeswitch` is the only provider
module with a data migration (connect_twilio / connect_asterisk ship none):

* **connect 19.0.4.0.0 pre-migration** (in the core module) renames the moved
  PBX tables to `_*_legacy` archives so the registry cleanup cannot drop them,
  and removes the sms.composer inherit view (the wizard moved to
  connect_twilio).
* **connect_freeswitch 19.0.2.0.0 pre-migration** stashes the
  `connect_fs_fifo` exten FKs (`exten`, `fallback_exten_id`) and the
  `fs_fifo_endpoint_rel` M2M rows into temporary `_mig_*` columns/tables and
  drops the stale constraints, so the fresh FK to the still-empty
  `connect_freeswitch_exten` table cannot abort the upgrade.
* **connect_freeswitch 19.0.2.0.0 post-migration** copies the legacy data
  **id-preserving** into the new models
  (`_connect_exten_legacy` → `connect_freeswitch_exten`, callflow(+choice,
  ring-users rel), number, endpoint, outgoing_callerid), remaps the exten
  `model` Reference strings (`connect.callflow` →
  `connect.freeswitch.callflow`, …), transfers the legacy `connect_user`
  columns (`exten`, `outgoing_callerid`) into the new per-provider columns,
  and restores the stashed fifo FKs.

---

## Deploy

### FreeSWITCH image (`deploy/`)

`oduist/freeswitch` is built from source (`v1.10.12`) with a curated
module list (sofia, fifo, verto, http_cache, piper_tts, …). Config
lives under `deploy/freeswitch/conf/`. `docker-entrypoint.sh` runs
sound-file download, TLS extraction from Traefik ACME, and now also
substitutes `FS_ESL_PASSWORD` into `event_socket.conf.xml`. The
baked-in ESL password is `ConnectNGESLPassword` (project-specific,
not the FreeSWITCH default `ClueCon`).

`vars.xml` defines the `us-ring` ringback tone (`%(2000,4000,440,480)`)
because the image wipes FreeSWITCH's stock configs; the dialplan
templates set `ringback` / `transfer_ringback` to `${us-ring}` before
every `bridge` so inbound callers hear ringing instead of silence
(issue #113, ADR-029).

### Firewall service image (`deploy/firewall/`)

`oduist/freeswitch-firewall` is a small Python container that:

* connects to FreeSWITCH via ESL (`mod_event_socket`);
* maintains the six-table-per-family `ipset` / `iptables` +
  `ip6tables` chain `connect_fw_voip` on the host kernel (IPv6 sets
  are the `6`-suffixed twins, e.g. `connect_fw_banned6`) — requires
  `--network host --cap-add NET_ADMIN`;
* exposes HTTP for `/firewall/sync`, `/firewall/api/*` and a Lit-based
  dashboard at `/firewall/`;
* calls Odoo HTTP controllers at `/freeswitch/firewall/api/*`
  authenticated with the shared `firewall_service_token` Bearer.

The original six-table / iptables design is captured in
**`specs/decisions/014-freeswitch-firewall-service.md`**; the shift
from portal-user RPC to shared-bearer HTTP controllers (v1.1.0) is
captured in **`specs/decisions/015-firewall-token-controllers.md`**;
IPv6 support (v1.2.0: parallel `family inet6` sets, `ip6tables` chain,
canonical entry normalization) is captured in
**`specs/decisions/037-firewall-ipv6-support.md`**.

Operational guide for admins lives in **`docs/admin/firewall.md`**.

---

## CDR webhook & call direction

`controllers/freeswitch_cdr.py` receives `mod_xml_cdr` POSTs at
`/freeswitch/webhook/cdr`, parses the XML into a dict, and hands it to
`connect.call.on_freeswitch_cdr`.

Call **direction** is resolved from the dialplan-stamped business direction,
not FreeSWITCH's transport-level direction. The dialplan sets
`odoo_call_direction` (`inbound` on inbound DID routes, `outgoing` on outgoing
routes — `data/fs_templates.xml`); `_parse_cdr_xml` reads it and
`connect.call._cdr_technical_direction` maps it to `technical_direction`
(`outgoing` → `outbound-api`, `inbound` → `inbound`). Only when the variable is
absent does it fall back to FreeSWITCH's native `<channel_data><direction>`.
This prevents `originate`-launched outbound calls — whose UA / origination leg
is `inbound` from FreeSWITCH's own perspective — from being mislabelled as
incoming. See **`specs/decisions/028-cdr-direction-from-dialplan-variable.md`**.

---

## Tests

`connect_freeswitch/tests/test_firewall.py` covers:

* whitelist / blacklist IP+CIDR validation and uniqueness;
* token validator on `connect.settings`;
* `fetch_config` / `fetch_whitelist` / `fetch_blacklist` /
  `report_event` / `report_heartbeat` / `report_applied`;
* `_cron_cleanup` retention logic;
* the Unban action (`is_banned` compute + `action_unban_ip`)
  with the service calls mocked out.

`tests/test_cdr_direction.py` covers CDR direction resolution: `_parse_cdr_xml`
extraction of `odoo_call_direction`, and `_cdr_technical_direction` preferring it
over the native FreeSWITCH direction (the issue #43 regression) with the
native-direction fallback.
