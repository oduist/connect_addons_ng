# Connect FreeSWITCH Module Specification

## Module Info

- **Name:** Oduist Connect FreeSWITCH
- **Technical:** `connect_freeswitch`
- **Depends:** `connect`, `web`
- **Application:** False
- **License:** Proprietary

## Overview

The `connect_freeswitch` module extends the core `connect` module with
FreeSWITCH-specific functionality. Like `connect_twilio` it follows the
abstract-core / concrete-integration pattern: core defines models and
abstract hooks, FreeSWITCH-side code adds fields and behaviour via
`_inherit`.

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
| `firewall_service_token` / `display_firewall_service_token` | Char | shared Bearer secret (masked; admin-only; validator requires ≥24 chars urlsafe) |
| `freeswitch_agent_password` / `display_freeswitch_agent_password` | Char | password for the `freeswitch_agent` portal user (masked; ≥12 chars, no whitespace) |
| `firewall_heartbeat_interval` | Integer | seconds, default 60 |
| `firewall_event_retention_days` | Integer | how long the audit log is kept; default 30 |
| `firewall_tcp_ports`, `firewall_udp_ports` | Char | comma-separated ports protected by the iptables chain |
| `firewall_banned_timeout` | Integer | auto-ban TTL (24 h default) |
| `firewall_authenticated_timeout` | Integer | trust TTL after a successful registration (7 days, sliding) |
| `firewall_expire_short_timeout` | Integer | challenge-response window (30 s) |
| `firewall_expire_long_timeout` | Integer | default-deny TTL after a challenge is sent but not answered (24 h) |

`write()` is extended to:
* validate the two secrets (length + character set) when an admin
  edits them in the UI;
* propagate a new password to the `freeswitch_agent` portal user
  record so subsequent XML-RPC logins use it;
* schedule a `/firewall/sync` POST via `cr.postcommit` whenever any
  `firewall_*` field changes.

### firewall.py — firewall models

| Model | Purpose |
|---|---|
| `connect.firewall.whitelist` | static IP / CIDR records that bypass all banning logic |
| `connect.firewall.blacklist` | static IP / CIDR records that are always blocked (manual permanent bans) |
| `connect.firewall.event` | audit log of every security-relevant event reported by the service |
| `connect.firewall.agent` | singleton holding service heartbeat data; entry point for service ↔ Odoo XML-RPC |

**Whitelist / Blacklist** share the same shape (`name`, `ip_or_cidr`,
`active`, `note`). `@api.constrains` validates the address with
`ipaddress.ip_network()` and enforces uniqueness per table. Each
`create` / `write` / `unlink` schedules `connect.firewall.agent._trigger_sync()`.

**Event** is read-only from the UI (`create=false edit=false`) — it is
populated only by the service via XML-RPC. The
`event_type` Selection covers: `auth_success`, `auth_fail`, `auto_ban`,
`manual_ban_applied`, `manual_unban_applied`, `whitelist_changed`,
`blacklist_changed`, `settings_changed`, `service_started`,
`service_error`. The `is_banned` computed flag, evaluated by polling
the service's live `/firewall/api/bans`, drives the Unban button.

**Agent (singleton)** holds `last_seen`, `version`, `esl_connected`,
`bans_count`, `authenticated_count`, `uptime_seconds` and a `status`
Selection (`online` / `stale` / `offline`) computed from `last_seen`
against `firewall_heartbeat_interval`.

`connect.firewall.agent` is also the **entry point for XML-RPC** the
service calls into:

| Method | Direction | Purpose |
|---|---|---|
| `fetch_config(*args, **kwargs)` | service → Odoo | returns `firewall_*` settings plus `firewall_service_token` |
| `fetch_whitelist()` | service → Odoo | active whitelist records (`ip_or_cidr`, `name`, `note`) |
| `fetch_blacklist()` | service → Odoo | active blacklist records |
| `report_event(payload, *args, **kwargs)` | service → Odoo | create one `connect.firewall.event`. Accepts a wrapped payload (`[{...}]`) too, because some XML-RPC clients insert an extra positional. |
| `report_heartbeat(payload, *args, **kwargs)` | service → Odoo | updates the agent singleton |
| `report_applied(ip, action, status="ok", message=None, *args, **kwargs)` | service → Odoo | updates `last_sync_at` and sends a bus notification to admins |
| `_trigger_sync(scope="all")` | Odoo (internal) | schedules a Bearer-authenticated POST to `<firewall_service_url>/firewall/sync` via `cr.postcommit` |
| `_call_service_unban(ip)` | Odoo (internal) | DELETE `/firewall/api/bans/<ip>` and log a `manual_unban_applied` event |
| `_fetch_live_banned_ips()` | Odoo (internal) | GET `/firewall/api/bans` to drive `connect.firewall.event.is_banned` |
| `_cron_reconcile()` | ir.cron | every 5 min, calls `_trigger_sync("all")` as a safety net |

The model module also defines `_first_dict(*values)`, a defensive
helper that flattens nested positional arguments and finds the dict
payload — needed because different RPC clients serialise positional
arguments slightly differently.

### Other models

Beyond firewall, the module contains:

| Model | Purpose |
|---|---|
| `connect.user` (`_inherit`) | adds WebRTC fields and dial-string generation |
| `connect.endpoint` (`_inherit`) | SIP endpoint management |
| `connect.exten` (`_inherit`) | extension number tooling |
| `connect.callflow` (`_inherit`) | callflow extension for FreeSWITCH-specific destinations |
| `connect.number` (`_inherit`) | DID assignment |
| `connect.freeswitch.gateway` | SIP gateway records, rendered into pjsip_wizard XML |
| `connect.freeswitch.outgoing_route` | outbound routing rules |
| `connect.freeswitch.template` | Jinja2 templates for dialplan / directory XML |
| `connect.fs_fifo` | mod_fifo queue records (ADR-013) |
| `connect.freeswitch.parking.slot` | call parking (ADR-012) |

---

## Security

### Groups (`security/firewall_security.xml`)

| Group | XML ID | Purpose |
|---|---|---|
| FreeSWITCH Agent | `connect_freeswitch.group_freeswitch_agent` | Identity used by the firewall service (and any future FreeSWITCH-side automation) when calling into Odoo. Comes with the `Role / Portal` implied membership so the user does not consume an enterprise seat. |

### Portal user (`data/res_users.xml`)

`user_freeswitch_agent` (login `freeswitch_agent`, `share=True`) is the
canonical identity used by FreeSWITCH-side services. The
`post_init_hook` / per-version migration moves it into `Role / Portal`
and `FreeSWITCH Agent`, then generates the initial password and the
firewall service token if they are not set.

### Access rules

See `security/access_rules.xml`. Highlights:

| Model | `connect_admin` | `connect_user` | `group_freeswitch_agent` |
|---|---|---|---|
| `connect.firewall.whitelist` | CRUD | read | read |
| `connect.firewall.blacklist` | CRUD | read | read |
| `connect.firewall.event` | read + unlink | read | create + read |
| `connect.firewall.agent` | read + write | read | read + write + create |
| `connect.settings` | (inherited) | (inherited) | read |

The agent user can never create or modify whitelist / blacklist
entries — those changes are strictly an admin action made through the
Odoo UI.

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
* a `Connect → PBX → Firewall` menu structure with sub-items
  `Agent Status`, `Whitelist`, `Blacklist`, `Events`.

`views/settings.xml`:
* extends the existing settings page with a `Firewall` page —
  Enabled toggle, Service URL, masked secrets with a 🔄 generator
  button next to the token, heartbeat interval, retention, ports,
  timeouts.

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

### Firewall service image (`deploy/firewall/`)

`oduist/freeswitch-firewall` is a small Python container that:

* connects to FreeSWITCH via ESL (`mod_event_socket`);
* maintains the six-table `ipset` / `iptables` chain `connect_fw_voip`
  on the host kernel — requires `--network host --cap-add NET_ADMIN`;
* exposes HTTP for `/firewall/sync`, `/firewall/api/*` and a Lit-based
  dashboard at `/firewall/`;
* talks to Odoo via XML-RPC under the `freeswitch_agent` portal user.

The full design — six ipset tables, challenge-response window, kernel
UA filter, direct-HTTP control plane between Odoo and the service —
is captured in **`specs/decisions/014-freeswitch-firewall-service.md`**.

Operational guide for admins lives in **`docs/admin/firewall.md`**.

---

## Tests

`tests/test_firewall.py` (gated test suite — symlinked from
`tests_suite/connect_freeswitch/tests/`) covers:

* whitelist / blacklist IP+CIDR validation and uniqueness;
* token / agent-password validators on `connect.settings`;
* `fetch_config` / `fetch_whitelist` / `fetch_blacklist` /
  `report_event` (incl. the wrapped-payload path) / `report_heartbeat` /
  `report_applied`;
* `_cron_cleanup` retention logic;
* the Unban action (`is_banned` compute + `action_unban_ip`)
  with the service calls mocked out.

24 tests, all green at the time of writing.
