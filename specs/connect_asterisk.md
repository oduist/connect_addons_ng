# Connect Asterisk Module Specification

## Module Info

- **Name:** Oduist Connect Asterisk
- **Technical:** `connect_asterisk`
- **Depends:** `connect`, `web`
- **Application:** False
- **License:** Proprietary

## Overview

The `connect_asterisk` module extends the core `connect` module with
Asterisk-specific functionality, ported from the legacy `asterisk_plus`
product. Like the other providers it follows the abstract-core /
concrete-integration pattern: core defines models and abstract hooks,
Asterisk-side code adds fields and behaviour via `_inherit`.

Unlike `connect_freeswitch`, the target deployment is an **existing
customer Asterisk** (FreePBX, Issabel, plain Asterisk 13–21) — the
module renders configuration snippets for the administrator to apply;
no Asterisk image is shipped.

It ships **two deliverables**:

1. The Odoo addon proper — models, views, controllers under
   `connect_asterisk/`.
2. A thin sidecar agent Docker image (`oduist/asterisk-agent`) under
   `deploy/agent/` that bridges AMI to the Odoo webhooks. See
   `specs/decisions/026-asterisk-sidecar-agent.md`.

Major features:
- AMI event pipeline: agent → `/asterisk/webhook/events` →
  `connect.channel` adapters → core `process_channel_event` /
  `process_call_event`;
- click-to-call via AMI `Originate` through the agent;
- MixMonitor recording upload (agent push) with core transcription;
- JsSIP web phone (WSS directly to the customer's Asterisk);
- dialplan-assist lookups (`CURL()` caller name / partner manager);
- pjsip wizard + manager.conf config generation from Jinja2 templates.

---

## Architecture

```
Asterisk (customer) ←AMI→ oduist/asterisk-agent (Docker sidecar)
                              │ POST /asterisk/webhook/events   (Bearer)
                              │ PUT  /asterisk/webhook/recording/<uid>.<ext>
                              │ POST /asterisk/webhook/heartbeat
                              │ GET  /asterisk/api/config       (bootstrap)
                              ▼
                           Odoo (connect_asterisk)
                              │ POST {agent}/originate, /ami_action, /sync
                              ▼
                           agent → AMI Action → Asterisk

JsSIP web phone (browser) ←WSS/SIP→ customer's Asterisk (no agent involved)
```

Both HTTP directions carry `Authorization: Bearer <asterisk_agent_token>`
(`secrets.compare_digest`). Event/recording webhooks dispatch under
`connect.user_connect_webhook`; bootstrap/lookup routes use `sudo()`
after the token check (ADR-015 pattern). Lookup routes also accept the
token as a `?token=` query parameter for dialplan `CURL()`.

## Models

### `connect.settings` (`models/settings.py`, `_inherit`)

Fields (all `asterisk_` prefixed): `asterisk_enabled` (master toggle),
agent connection (`asterisk_agent_url`, `asterisk_agent_token` +
masked `display_asterisk_agent_token`, in `PROTECTED_FIELDS`), AMI
bootstrap (`asterisk_ami_host/port/user/password`, `asterisk_events`),
originate (`asterisk_originate_context`, `asterisk_originate_timeout`),
`asterisk_recordings_enabled`, web phone (`asterisk_phone_enabled`,
`asterisk_websocket_url`, `asterisk_sip_proxy`, `asterisk_sip_realm`,
`asterisk_stun_server`, `asterisk_phone_trace_sip`, transfer
sequences, `asterisk_transfer_contact_search`), status fields
(`asterisk_agent_status/version`, `asterisk_last_heartbeat`,
`asterisk_core_status`).

Methods:
- `asterisk_agent_request(path, payload, method, timeout, raise_exc)` —
  Bearer HTTP to the agent;
- `asterisk_ami_action(action, ...)` — generic AMI action passthrough;
- `asterisk_agent_sync(scope)` — postcommit `/sync` nudge, gated on
  `asterisk_enabled` (fired from `write()` on `asterisk_*` changes,
  status fields excluded);
- `originate_call(number, res_model, res_id, user)` — implements the
  core click-to-call contract (`connect.call.redial` calls it):
  pre-creates the first leg (`technical_direction='outbound-api'`,
  `sid=ChannelId`) so later AMI events update instead of duplicate,
  then POSTs an AMI `Originate` per originate-enabled endpoint;
- `asterisk_get_agent_config()` — payload of `/asterisk/api/config`;
- `asterisk_get_phone_settings()` — JsSIP web phone configuration;
- `asterisk_ping_agent()` / `check_asterisk_status()` — form buttons.

### `connect.channel` (`models/channel.py`, `_inherit`)

Fields: `asterisk_channel` (e.g. `PJSIP/101-0000af`),
`asterisk_answered` (Datetime), `asterisk_recording_file`.

AMI adapters (all `@api.model`, dispatched by the webhook controller),
each builds a generic dict and calls core `process_channel_event` +
`connect.call.process_call_event`:

| Handler | AMI event | Semantics |
|---|---|---|
| `on_ami_new_channel` | `Newchannel` | primary leg (`Uniqueid==Linkedid`) → `technical_direction='inbound'`; secondary leg → `'outbound-dial'` + `parent_sid=Linkedid`; endpoint matching via `connect.endpoint.get_endpoint_by_channel` fills `caller_pbx_user_id`/`called_pbx_user_id`; pre-created originate legs keep `'outbound-api'`; `Local/` channels skipped |
| `on_ami_new_state` | `Newstate` (Up only) | `status='in-progress'`, stamps `asterisk_answered` |
| `on_ami_new_connected_line` | `NewConnectedLine` | fills missing/`s` caller/called numbers |
| `on_ami_hangup` | `Hangup` | answered → `completed` + duration from `asterisk_answered`; unanswered via `UNANSWERED_CAUSE_MAP` (Q.850: 16→canceled, 17/21→busy, 18/19→no-answer, 26→canceled, else failed); replays are idempotent; runs orphan channel/recording relink |
| `on_ami_originate_response_failure` | `OriginateResponse` (Failure) | leg `failed`, `error_data` on the call, sticky notification to the originator |
| `on_ami_var_set` | `VarSet` (`MIXMONITOR_FILENAME`) | stores the recording path |

`_asterisk_relink_orphans()` mirrors the FreeSWITCH orphan handling
(secondary legs and recordings arriving before their parent).

### `connect.endpoint` (`models/endpoint.py`, `_inherit`)

`asterisk_channel` (dial string, format-checked, unique),
`asterisk_sip_user` (computed: `PJSIP/101 → 101`, stored),
`asterisk_sip_password` (auto passphrase, `groups=connect.group_admin`,
regenerate button — ADR-022 style), `asterisk_sip_transport`
(udp/tcp/webrtc), `asterisk_originate_enabled`,
`asterisk_originate_context`, `asterisk_auto_answer_header`.
`get_endpoint_by_channel(name)` strips the `-suffix` and matches the
dial string. `_get_originate_variables()` builds the `Variable` list
(REALCALLERIDNUM, auto-answer header — `PJSIP_HEADER` vs
`SIPADDHEADER` by channel tech, per-user extra vars).

### `connect.user` (`models/user.py`, `_inherit`)

`asterisk_originate_vars`, web phone preferences (`phone_ring_volume`,
`mask_call_number`, `call_popup_is_enabled/sticky`).
`get_user_by_uri()` implements the core stub: matches
`sip:<user>@host` / bare numbers against endpoint SIP users, then
exten numbers. `search_pbx_users()` powers the phone contacts search.

### `connect.recording` (`models/recording.py`, `_inherit`)

`action_fetch_from_asterisk()` — pull-fallback button asking the agent
to re-upload a missed recording. Creation/transcription is all core.

### `connect.asterisk.template` (`models/ast_template.py`, new model)

Jinja2 config snippets (`sip_peer_header`, `sip_peer`, `manager_conf`)
rendered for the customer's PBX. **Access: admin CRUD only; Connect
User and webhook groups have no access** (admin-only infrastructure
model). Defaults in `data/ast_templates.xml`.

### `res.users` (`models/res_users.py`, `_inherit`)

`get_sip_user_config(user_id)` — own-record-only web phone credentials
(first webrtc endpoint) + phone preferences.

## Controllers

### `controllers/webhooks.py` — agent → Odoo (Bearer + webhook user)

- `POST /asterisk/webhook/events` — batch of trimmed AMI events;
  `EVENT_HANDLERS` maps `Event` → channel adapter;
- `PUT|POST /asterisk/webhook/recording/<filename>` — raw audio,
  `<uniqueid>.<ext>`; dedupe by `call_sid`, orphan-tolerant;
- `POST /asterisk/webhook/heartbeat` — agent status into settings.

### `controllers/agent_api.py` — bootstrap & dialplan assist (Bearer + sudo)

- `GET /asterisk/api/config` — AMI credentials, event filter,
  recording toggle;
- `GET /asterisk/api/get_caller_name?number=` — partner name for
  `CALLERID(name)`;
- `GET /asterisk/api/get_partner_manager?number=&exten=` — salesperson
  dialstring/exten routing;
- `GET /asterisk/api/get_user_data_by_did?did=` — DID → user dialstring
  (`connect.number` destination=user);
- `GET /asterisk/api/sip_peers` — pjsip wizard config for all endpoints;
- `GET /asterisk/api/manager_conf` — AMI account snippet.

## Frontend (`static/src/`)

JsSIP web phone folded in from `asterisk_plus_phone`, components
aligned with the `connect_twilio` phone widget (already core-wired):

- `js/core.js` — service: gates on `connect.group_user/admin`,
  `asterisk_get_phone_settings().phone_enabled` and
  `res.users.get_sip_user_config`; registers systray + main component;
- `components/phone/` — JsSIP UA (WSS to the customer's Asterisk),
  call control, transfer/forward DTMF sequences, BroadcastChannel
  multi-tab coordination;
- `components/{calls,contacts,favorites,tray}/` — core-model-wired
  (`connect.call.get_widget_calls`, `connect.favorite`,
  `res.partner.api_get_partner`, `connect.user`);
- `widgets/phone_field/` — click-to-dial: web phone when active,
  otherwise server-side `connect.settings.originate_call`;
- `lib/jssip.min.js`, sounds, icomoon icon font.

## Security

- No new groups; reuses `connect.group_user/admin/webhook`.
- New model `connect.asterisk.template`: admin-only (see above).
- All other data lives on core models with existing ACLs.
- Secrets: `asterisk_agent_token` masked via `PROTECTED_FIELDS` +
  `groups=connect.group_admin`; `asterisk_sip_password` admin-only,
  exposed to the owner exclusively through `get_sip_user_config`.

## Core contract — implemented vs intentionally not implemented

| Core hook | Status |
|---|---|
| `connect.settings.originate_call` | ✔ AMI Originate via agent |
| `connect.user.get_user_by_uri` | ✔ endpoint SIP user / exten match |
| `connect.channel` event feed | ✔ AMI adapters |
| `connect.recording` ingestion | ✔ webhook upload |
| `connect.message.send` | ✘ no SMS transport on plain Asterisk (phase 2+) |
| `connect.number.route_call` | ✘ inbound routing stays in the customer's dialplan; DID-assist lookup provided instead |

Deferred: voicemail (MiniVM), spy/whisper/barge, retention crons,
multi-server, job-poll command channel for NATed agents (ADR-026 §6).

## Sidecar agent (`deploy/agent/`)

Python 3.12 asyncio package `connect_asterisk_agent`, image
`oduist/asterisk-agent` (tag = short manifest version when
`deploy/agent/**` changes; multi-arch amd64+arm64). Modules: `ami.py`
(hand-rolled AMI client: login, reconnect+backoff, Ping keepalive,
ActionID correlation, EventList collection), `constants.py` (event
allowlist + guard filters), `ami_handler.py` (filter → trim → stamp
`EventTime` → enqueue), `odoo_client.py` (batched outbox),
`call_state.py` (in-memory registry, TTL), `recordings.py` (stability
wait, retry, state persistence), `reconciler.py` (config pull +
`CoreShowChannels` healing with synthetic hangups), `http_server.py`
(FastAPI: `/originate`, `/ami_action`, `/recording_fetch`, `/sync`,
`/healthz` liveness + `/asterisk/healthz` readiness — ADR-017),
`__main__.py` (task supervisor). Unit tests under `deploy/agent/tests`
(plain pytest, not the gated suite).

Customer-side requirements: a `manager.conf` user with
`read = call,dialplan,user`, `write = originate,call,reporting`; the
monitor directory mounted into the agent container for recordings; no
dialplan changes.

## Tests

`connect_asterisk/tests/__init__.py` — gated loader →
`tests_suite/connect_asterisk/tests/`:
`test_webhook_events.py`, `test_originate.py`,
`test_recording_webhook.py`, `test_endpoint.py`, `test_settings.py`,
`test_agent_api.py`, `test_phone_config.py` (+ `common.py`).
