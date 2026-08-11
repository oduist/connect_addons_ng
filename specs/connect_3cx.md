# Connect 3CX Module Specification

## Module Info

- **Name:** Oduist Connect 3CX
- **Technical:** `connect_3cx`
- **Version:** 18.0.1.0.0
- **Depends:** `connect`, `web`
- **Application:** False
- **License:** Proprietary

## Overview

The `connect_3cx` module integrates an existing customer **3CX V20** PBX
with the Connect ledger at two tiers:

- **Phase 1 (ADR-034, PRO or AI edition)** — 3CX's server-side CRM
  integration: the 3CX System Service executes an XML template on every
  external call, calling back into Odoo webhook controllers (lookup,
  journal at call end, contact creation).
- **Phase 2 / deep tier (ADR-035, AI edition 8SC+ only, opt-in)** — a
  sidecar agent (`oduist/3cx-agent`, `deploy/agent/`) holding the Call
  Control WebSocket for **live call events**, server-side click-to-call
  through Call Control makecall, and an XAPI poller that downloads
  **recording audio** into Odoo (core transcription applies).

Unlike the other providers, `connect_3cx` owns **no PBX configuration
models and no phone widget**: 3CX keeps numbering, routing, devices and
the softphone (3CX has no third-party WebRTC/WSS access). The module is
`connect.settings` + `connect.user` + `connect.channel` extensions,
webhook controllers, a generated CRM template, and the agent image.

Major features:
- contact lookup at call arrival (caller name + screen pop in 3CX
  clients, linked to the Odoo partner form);
- call journaling at call end → `connect.channel`/`connect.call` ledger
  records via the core `process_channel_event`/`process_call_event`
  pipeline (idempotent, deterministic SID);
- 3CX AI artifacts (recording URL, transcription, summary, sentiment)
  stored on a `connect.recording` reference record;
- contact creation from 3CX clients → `res.partner`;
- click-to-call via the 3CX Web Client dial URL
  (`/webclient/#/call?phone=...`);
- CRM template generator (download from the settings form, instance URL
  and API key pre-filled).

**Limitations:** on the phase-1 tier calls appear in the ledger only
after hangup (no live channel states) and recording audio is not
downloadable (URL reference only); internal 3CX calls are never
reported by the CRM template; no SMS surface at any tier; no web phone
at any tier. The deep tier removes the live-events and recording-audio
limits but is developed **without a live 3CX validation pass** (mock
tests only — ADR-035); revalidate against a real PBX before GA.

---

## Architecture

```
3CX System Service (customer PBX, V20 PRO/AI)
   │  executes the generated CRM template on every external call
   │  GET  /3cx/webhook/lookup?number=..&direction=..   (call arrival)
   │  POST /3cx/webhook/report_call                     (call end)
   │  POST /3cx/webhook/create_contact                  (from 3CX client)
   ▼
Odoo (connect_3cx) — X-Connect-Api-Key (or Bearer) checked with
secrets.compare_digest; ledger writes under connect.user_connect_webhook

Click-to-call: originate_call() override returns ir.actions.act_url →
browser opens https://<pbx>/webclient/#/call?phone=<number> (the user's
own 3CX Web Client places the call; it lands in the ledger via the
journal webhook).

Deep tier (ADR-035, threecx_agent_enabled):

3CX PBX (AI 8SC+) ←OAuth2+WSS/REST→ oduist/3cx-agent (Docker sidecar)
                        │ POST /3cx/webhook/events      (Bearer, batches)
                        │ PUT  /3cx/webhook/recording/<recid>.<ext>?meta
                        │ POST /3cx/webhook/heartbeat
                        │ GET  /3cx/api/config          (bootstrap)
                        ▼
                     Odoo (connect_3cx)
                        │ POST {agent}/originate, /sync
                        ▼
                     agent → POST /callcontrol/{dn}/makecall → 3CX

The agent is the sole consumer of a dedicated 3CX API client
application (single-active-token rule); on Upsert WS events it re-GETs
the entity and forwards the normalized participant state; ReportCall
becomes a merger (transcript/summary/recording URL attach to the
agent-created call instead of duplicating it).
```

## Models

### `connect.settings` (`models/settings.py`, `_inherit`)

Fields (all `threecx_` prefixed): `threecx_enabled` (master toggle,
gates all webhook routes), `threecx_pbx_url` (3CX web-client base URL
for the dial URL), `threecx_api_key` + masked
`display_threecx_api_key` (in `PROTECTED_FIELDS`; min 24 chars,
`[A-Za-z0-9_-]`), status stamps `threecx_last_lookup` /
`threecx_last_journal` (written by the webhook controllers).

Methods:
- `threecx_generate_api_key()` — form button; routes the fresh key
  through the display field so the core protected-fields flow stores
  and masks it;
- `threecx_get_crm_template()` — renders
  `templates/crm_template.xml` (`string.Template`, `$odoo_url` /
  `$api_key` placeholders) with `api_url`/`web_base_url` and the stored
  key;
- `threecx_download_template()` — form button; ensures a key exists and
  returns an `act_url` to `/3cx/template`;
- `originate_call(number, ...)` — dispatcher override (key `'3cx'`,
  ADR-031 pattern): returns an `ir.actions.act_url` opening the 3CX Web
  Client dial URL. Requires `threecx_enabled` + `threecx_pbx_url`.

The module appends `connect_3cx` to `ODUIST_MODULES` and generates the
API key in `post_init_hook` (`setup_threecx_api_key(env)`).

Deep-tier fields (ADR-035): `threecx_agent_enabled`,
`threecx_agent_url`, `threecx_client_id`, `threecx_client_secret` +
masked `display_threecx_client_secret` (in `PROTECTED_FIELDS`),
`threecx_recordings_enabled`, `threecx_originate_timeout`, status
`threecx_agent_status/version`, `threecx_last_heartbeat`. Deep-tier
methods: `threecx_agent_request()` (Bearer HTTP to the agent),
`threecx_agent_sync()` (postcommit `/sync` nudge fired from `write()`
on `threecx_*` changes, status fields excluded), `threecx_ping_agent()`
(form button), `threecx_get_agent_config()` (payload of
`/3cx/api/config`), `_threecx_originate_via_agent()` (POST
`{agent}/originate`; pre-creates the `3cxcc-<callid>-<legid>` leg from
the makecall response; returns None on agent failure so
`originate_call()` falls back to the dial URL).

### `connect.channel` (`models/channel.py`, `_inherit` — deep tier)

Fields: `threecx_callid` (indexed), `threecx_legid`,
`threecx_answered` (Datetime, the `asterisk_answered` pattern).

`on_threecx_participant_event(event)` maps a normalized agent event
into core `process_channel_event` + `process_call_event`:

- SID = `3cxcc-<callid>-<legid>`, fallback `3cxcc-<sha1(entity)[:16]>`;
- `_threecx_leg_kind(state, dn)` — the single, test-pinned direction
  heuristic: `originated_by_dn == dn` or status `Dialing` → outbound
  (`'outbound-api'` + `caller_pbx_user` by `threecx_exten`), else
  inbound (`'inbound'` + `called_pbx_user`); an existing channel never
  flips direction (pre-created originate legs stay `outbound-api`);
- upsert: `Connected` → `in-progress` + `threecx_answered` stamp, else
  `ringing`; replays after a final status are ignored;
- remove: `completed` with duration `ts − threecx_answered` when
  answered, else `no-answer`.

### `connect.user` (`models/user.py`, `_inherit`)

`originate_provider` `selection_add` `('3cx', '3CX')`; `threecx_exten`
(plain Char — 3CX numbering is owned by the PBX; used by the journal
webhook to resolve the agent) contributed to `_pbx_number_fields()`.

## Controllers (`controllers/webhooks.py`)

All `/3cx/webhook/*` routes: `auth='none'`, `csrf=False`,
`readonly=False` (Odoo 19 `auth='none'` routes are read-only by
default), gated on `threecx_enabled` + API key
(`X-Connect-Api-Key` header, `Authorization: Bearer` also accepted,
`secrets.compare_digest`).

### `GET /3cx/webhook/lookup?number=&direction=`

Contact lookup at call arrival (both directions). Resolves the partner
via core `res.partner.get_partner_by_number()` (sudo — read-only
partner data, same trust level as the Asterisk caller-name lookups) and
returns:

```json
{"contact": {"id": 42, "url": "<base>/web#id=42&model=res.partner&view_type=form",
  "first_name": "", "last_name": "...", "company_name": "...",
  "entity_type": "Person|Company", "phone_business": "...",
  "phone_mobile": "...", "email": "..."}}
```

`{}` when there is no match. Stamps `threecx_last_lookup`.

### `POST /3cx/webhook/report_call`

Call journal at call end. Payload keys (all strings, produced by the
template `PostValues`): `call_type` (`Inbound`/`Missed`/`Outbound`/
`Notanswered`), `direction`, `number`, `contact_name`, `entity_id`,
`entity_type`, `queue_extension`, `agent`, `agent_email`, `duration`
(hh:mm:ss), `start_utc_millis`, `established_utc_millis`,
`end_utc_millis`, `recording_url`, `transcription`, `summary`,
`sentiment`.

Processing (under `connect.user_connect_webhook`):
1. SID = `3cx-` + sha1(`agent|number|start_utc_millis|call_type`)[:24]
   — the template has no call-id variable; replays dedupe by content.
2. `CALL_TYPE_MAP`: Inbound/Missed → `technical_direction='inbound'` +
   `called_pbx_user` from `threecx_exten`, status
   `completed`/`no-answer`; Outbound/Notanswered →
   `'outbound-api'` + `caller_pbx_user`, status
   `completed`/`no-answer`.
3. Duration: `established→end` millis when both present, else parsed
   `hh:mm:ss`; 0 for unanswered.
4. Core `process_channel_event` + `process_call_event`; `entity_id`
   (our own lookup output = partner id) backfills `channel.partner`
   when number matching found nothing.
5. When `recording_url`/`transcription`/`summary` present: a
   `connect.recording` reference is created with `skip_transcription`
   context (`media_url` points into the 3CX web client — audio not
   downloadable; 3CX AI transcript/summary fill `transcript`/`summary`;
   sentiment is appended to the summary HTML). `call.summary` is filled
   when empty.
6. Stamps `threecx_last_journal`.

### `POST /3cx/webhook/create_contact`

Creates a `res.partner` from `first_name`/`last_name`/`number`/`email`/
`company` (token-gated `sudo()` — the webhook group has no partner ACL;
blast radius documented in ADR-034) and returns the full contact JSON
(single scenario, no fetch chain).

### Deep-tier routes (ADR-035)

Gated on the token **and** `threecx_agent_enabled` (a stale agent stops
writing the moment the admin disables the tier):

- `POST /3cx/webhook/events` — batch of normalized participant events,
  dispatched to `connect.channel.on_threecx_participant_event` under
  the webhook user;
- `PUT/POST /3cx/webhook/recording/<recid>.<ext>?callid=…` — recording
  audio from the agent's XAPI poller; deduped by `(sid, source='3cx')`,
  matched to the channel by `threecx_callid` (orphan `call_sid`
  `3cxrec-<recid>` otherwise); **no** `skip_transcription` — this is
  real audio, core transcription applies;
- `POST /3cx/webhook/heartbeat` — agent status stamps.
- `GET /3cx/api/config` (`controllers/agent_api.py`, Bearer + `sudo()`)
  — agent bootstrap payload (PBX URL, 3CX client credentials,
  recordings toggle).

In deep mode `report_call` first calls `_merge_into_agent_channel()`:
match an agent-created channel (`sid like '3cxcc-%'`, same
extension/number leg shape, `create_date` within ±180 s of
`start_utc_millis`) and attach the 3CX-AI-only artifacts
(transcript/summary/recording URL fill-if-empty on the channel's
recording, or a reference recording when the poller produced none);
falls back to the phase-1 creation path when nothing matches.

### `GET /3cx/template`

`auth='user'` + `connect.group_admin` check; streams the rendered CRM
template as `odoo_connect_3cx.xml`.

## CRM template (`templates/crm_template.xml`)

3CX V20 server-side template, `string.Template` placeholders
`$odoo_url`/`$api_key` substituted at download. Structure:
`<Number Prefix="Plus" MaxLength="[MaxLength]"/>`, custom-header auth
(`Authentication Type="No"` + `X-Connect-Api-Key` header per request),
three scenarios:
- lookup (empty Id): GET with `[[Number].Replace("+","%2B")]` +
  `[CallDirection]`; Rules anchor `contact.id`; outputs ContactUrl,
  EntityId/EntityType, name/phones/email (`Od*` variables to avoid
  clashing with 3CX predefined names);
- `ReportCall`: `PostValues`/JSON per the 3CX template spec;
  `SkipIf="[ReportCallEnabled]!=True"` only — **not** gated on
  `[EntityId]`, the ledger records unmatched calls too;
- `CreateContactRecordFromClient`: POST + full-record response
  (outputs populated directly).

Requires 3CX V20 (`RecordingUrl`/`Transcription`/`Summary`/`Sentiment`
variables do not exist on older releases). 3CX loads templates at
service start; template changes may require a 3CX service restart.

## Frontend

`static/src/widgets/phone_field/` — the per-provider phone-field patch
(deliberately duplicated, ADR-031): awaits
`connect.settings.originate_call` and executes a returned action dict
via the action service (the 3CX provider returns `act_url`). Core
`connect.call.redial()` returns the provider result for the same
reason. Co-installation keeps the last-loaded patch (ADR-032-style
caveat) — acceptable because every patch routes through the core
dispatcher.

## Security

No new models → no new ACLs. Webhook ledger writes run under the core
webhook user/group; lookup and contact creation are token-gated
`sudo()` (documented in ADR-034).

## Menus

**3CX** submenu under the Connect app (sequence 50): Configuration →
Settings (standalone `connect.settings` form via
`open_settings_form("connect_3cx.connect_settings_form_threecx", ...)`,
admin-only).

## Sidecar agent (`deploy/agent/`, `oduist/3cx-agent` — ADR-035)

Python package `connect_3cx_agent` on the asterisk-agent skeleton
(ADR-026): asyncio tasks + FastAPI, batched event outbox, config pull
with a JSON runtime cache, debounced reconciler, heartbeat. Modules:

- `tcx_api.py` — the process-wide 3CX token owner (client_credentials
  at `POST /connect/token`, proactive refresh at 80% of expires_in,
  single retry on 401) + Call Control (`/callcontrol`, makecall) and
  XAPI helpers (`Recordings` OData listing, `Pbx.DownloadRecording`);
- `ws.py` — `wss://<pbx>/callcontrol/ws` loop (Bearer, exponential
  backoff, token invalidation on failure, reconcile on reconnect);
- `handler.py` + `state.py` — participant registry: Upsert → re-GET
  entity → store + emit; Remove → emit last-known state; synthetic
  removes for the reconciler;
- `recordings.py` — XAPI poller tracking the highest seen recording id
  in the state file; defensive metadata pass-through, stops advancing
  past a failed upload (Odoo dedupes by recording id);
- `reconciler.py` — `config` scope (pull `/3cx/api/config`, cache,
  invalidate token on credential change) + `participants` scope
  (diff `GET /callcontrol` dump against the registry);
- `http_server.py` — `/originate`, `/sync`, `/api/status`, `/healthz`,
  `/3cx/healthz` (Bearer = shared `threecx_api_key`).

Env bootstrap: `ODOO_URL`, `AGENT_TOKEN` (+ optional `PBX_URL`,
`CLIENT_ID`, `CLIENT_SECRET`, `VERIFY_TLS`). Image policy: same as
asterisk-agent (multi-arch, tag = short manifest version, rebuilt only
when `deploy/agent/` changes); **publish only after a live-3CX smoke
test**. Agent unit tests: `deploy/agent/tests/` (pytest, mock-based).

## Requirements on the 3CX side

- 3CX V20, **PRO or AI** edition (server-side CRM integration is not
  available on Free/Basic/SMB);
- template uploaded in Admin Console → Integrations → CRM;
- 3CX journals **external** calls only, one record per call, at call
  end;
- deep tier additionally: **AI edition, 8SC+**, a dedicated API client
  application (Call Control + Configuration API scopes, System Owner
  role for recordings) with the monitored extensions enumerated on it
  in the 3CX console.
