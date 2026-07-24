# 035 — 3CX provider, phase 2: Call Control sidecar agent (deep tier)

## Status

Accepted

## Context

Phase 1 (ADR-034) integrates 3CX through the server-side CRM template:
calls reach the ledger only after hangup, click-to-call is a browser
URL, recording audio never leaves the PBX. The 3CX **AI edition (8SC+)**
additionally licenses two web APIs on V20:

- the **Call Control API** — REST under `/callcontrol` plus a WebSocket
  event stream at `wss://<pbx>/callcontrol/ws` delivering
  Upsert/Remove/DTMF notifications for the API client's Route Point and
  the **explicitly enumerated monitored extensions**;
- the **XAPI** (`/xapi/v1/`, OData) — configuration REST incl.
  `Recordings` listing and `Pbx.DownloadRecording` audio download.

Both authenticate with OAuth2 client_credentials against
`POST /connect/token` (60-minute tokens, **one active token per client
application** — a client's token is invalidated by the next issue).
Odoo workers cannot hold a persistent WebSocket, and the polling the
XAPI would otherwise require does not belong in request workers — the
same constraint that produced the Asterisk sidecar (ADR-026).

This phase is developed **without a live 3CX installation**: the
Call Control event payloads are under-documented (community-confirmed:
"sparse events", re-GET pattern), so every 3CX-facing mapping is
isolated and covered by mock-based tests; a live-validation pass is an
explicit follow-up before productizing.

## Decision

### 1. Sidecar `oduist/3cx-agent`, asterisk-agent architecture

A new Docker service under `connect_3cx/deploy/agent/`
(`connect_3cx_agent` package) reusing the ADR-026 skeleton: asyncio
tasks + FastAPI, batched event outbox to Odoo, config pull with a JSON
runtime cache, debounced reconciler, heartbeat loop. What replaces the
AMI machinery:

- a **token manager** (`tcx_api.py`): client_credentials against the
  PBX, proactive refresh at ~80% of `expires_in`, single-flight; the
  agent must be the **only consumer** of its 3CX client application
  (single-active-token rule) — customers create a dedicated API client
  for the agent;
- a **Call Control WebSocket loop** with Bearer auth and
  exponential-backoff reconnect; on every `Upsert` the agent re-GETs
  the changed entity (the WS payload only names it), keeps the last
  state in a TTL-bounded participant registry, and on `Remove` emits
  the registry's final state — Odoo never has to fetch anything;
- an **XAPI recording poller**: tracks the highest seen recording id in
  the agent state file, lists newer `Recordings`, downloads the audio
  and PUTs it to Odoo (deep tier gets real audio → core OpenAI
  transcription applies, unlike phase 1's URL references).

### 2. One shared secret; 3CX credentials live in Odoo

Agent ⇄ Odoo both directions reuse the phase-1 `threecx_api_key` as
`Authorization: Bearer` (`secrets.compare_digest`). The 3CX
`client_id`/`client_secret` (Admin Console → Integrations → API, with
both Call Control and Configuration API scopes) are stored on
`connect.settings` and served to the agent via `GET /3cx/api/config`
(Bearer + `sudo()`, the ADR-015/026 bootstrap pattern); the agent
caches them in its runtime JSON so it can boot while Odoo is down.
Env vars (`ODOO_URL`, `AGENT_TOKEN`) bootstrap the agent; everything
else is managed from the Odoo settings form.

### 3. Normalized participant events; heuristic mapping in one place

The agent POSTs batches to `/3cx/webhook/events` (webhook-user
dispatch, ADR-026 pattern):

```json
{"event": "upsert|remove", "entity": "/callcontrol/101/participants/5",
 "dn": "101", "participant_id": 5, "ts": 1751900000.0,
 "answered_at": 1751900012.0,
 "state": {"status": "Dialing|Ringing|Connected", "party_caller_id": "...",
            "party_caller_name": "...", "party_did": "...",
            "callid": 17, "legid": 2, "originated_by_dn": "", ...}}
```

`connect.channel.on_threecx_participant_event` maps them into the core
pipeline:

- SID = `3cxcc-<callid>-<legid>` (participant-stable across updates;
  fallback `3cxcc-<sha1(entity|dn)>` when ids are missing);
- direction: `Ringing` → inbound leg (`technical_direction='inbound'`,
  `called_pbx_user` = `connect.user` with `threecx_exten == dn`);
  `Dialing` or `originated_by_dn == dn` → outbound leg
  (`'outbound-api'`, `caller_pbx_user`). The field semantics are
  under-documented, so the whole heuristic lives in one function
  (`_threecx_leg_kind`) with tests pinning current behavior;
- `Connected` upsert → `in-progress` + `threecx_answered` stamp (new
  channel field, the `asterisk_answered` pattern); `remove` →
  `completed` with duration from the stamp when answered, else
  `no-answer`;
- a reconcile dump (`GET /callcontrol`) feeds synthetic removes for
  participants 3CX no longer lists (heals missed WS events).

### 4. Originate through the agent, dial-URL as fallback

With the agent enabled, `originate_call()` POSTs
`{agent}/originate {dn, destination, timeout}`; the agent calls
`POST /callcontrol/{dn}/makecall` and returns the 3CX response. When
the response carries `CallId`/`LegId`, Odoo pre-creates the leg
(`technical_direction='outbound-api'`, SID `3cxcc-<callid>-<legid>`) so
WS events update instead of duplicate — the ADR-026 originate pattern.
When the agent is disabled **or unreachable**, the override falls back
to the phase-1 Web Client dial URL, so click-to-call never hard-fails.

### 5. Phase-1 journal becomes a merger in deep mode

With the agent enabled, live events own channel creation, and the
`ReportCall` webhook would duplicate every call (it carries no
call-id). `report_call` therefore first looks for a recent
agent-created channel — same agent extension, same external number,
start time within ±3 minutes — and **merges** into it: 3CX AI
transcript/summary/recording-URL attach to the existing call (this
data only exists in the CRM-template payload). Only when nothing
matches does it fall back to creating the phase-1 post-factum record.
The CRM template itself is unchanged — lookup/screen-pop and contact
creation still come from phase 1.

### 6. No new models, again

`connect.settings` gains `threecx_agent_*` fields (toggle, agent URL,
client id/secret with masked display twin, recordings toggle, status
stamps) and `connect.channel` gains `threecx_callid`, `threecx_legid`,
`threecx_answered` — all `_inherit`, no new ACL surface. Recording
uploads reuse the core `connect.recording` webhook-group ACLs.

### 7. Intentionally not implemented in phase 2

- Automating the monitored-extensions list (stays a documented manual
  step in the 3CX console; XAPI automation is unverified).
- Call control verbs beyond makecall (answer/divert/transferto) and the
  PCM audio stream (a future AI-bot surface).
- XAPI user sync into `connect.user`.
- Publishing the Docker image: built from `deploy/agent/`, tagged by
  the short manifest version and multi-arch **at release time, after a
  live-3CX smoke test** — not from this branch (no live PBX available).

## Consequences

- Deep tier works only on 3CX V20 AI (8SC+) with a dedicated API client
  app; everything else keeps the phase-1 behavior — the module degrades
  gracefully tier by tier.
- All 3CX-facing parsing is based on documented + community-confirmed
  payload shapes and is verified only against mocks; the participant
  mapping and the recordings-poller field handling are deliberately
  defensive (unknown fields ignored, missing ids → fallbacks) and must
  be revalidated against a live PBX before GA.
- The agent is stateless apart from the participant registry and a
  small JSON state file (runtime config + last recording id); safe to
  restart at any time; reconcile heals both directions.
- Odoo→agent reachability has the same asymmetry as ADR-026 §6 (cloud
  Odoo + NATed PBX): originate falls back to the dial URL, events are
  outbound-only and unaffected.
