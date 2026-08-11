# 034 — 3CX provider, phase 1: server-side CRM template (`connect_3cx`)

## Status

Accepted

## Context

3CX V20 offers four integration surfaces, all researched July 2026:

1. **Server-side CRM integration** (XML template executed by the 3CX
   System Service on every external call) — available on the PRO and AI
   editions;
2. **Call Control API** (REST + WebSocket event stream) and **XAPI**
   (OData configuration REST API, incl. recording download) — gated to
   the AI edition (ex-Enterprise), 8SC minimum;
3. **CDR output** (TCP socket / files) — self-hosted instances only;
4. Third-party SIP registration — plain SIP only. 3CX has **no
   SIP-over-WebSocket** and explicitly refuses third-party WebRTC
   clients, so a JsSIP web phone (the `connect_asterisk` approach) is
   impossible on any edition. There is also no third-party SMS surface.

The market (MuK, Serpent, Softhealer, …) ships Odoo connectors built on
surface 1 only. Deep integration (live channel events via a sidecar
holding the Call Control WSS, XAPI recording pulls) is architecturally
close to `connect_asterisk` (ADR-026) but addresses only AI-edition
customers; it is deferred to a phase-2 ADR.

## Decision

Phase 1 ships `connect_3cx` on the CRM-template surface, covering the
PRO + AI market:

### 1. No new models

The module only `_inherit`s `connect.settings` (fields prefixed
`threecx_`: master toggle, PBX web-client URL, webhook API key +
masked display twin in `PROTECTED_FIELDS`, last lookup/journal status
stamps) and `connect.user` (`threecx_exten`, `originate_provider`
selection key `'3cx'`, `_pbx_number_fields()` contribution). No PBX
configuration models: numbering, routing and devices stay entirely in
3CX. Consequently the module adds **no ACL surface** — webhook
processing reuses the core webhook user and webhook-group ACLs.

### 2. Webhook controllers under `/3cx/webhook/*`

Three routes, mirroring the repo webhook conventions
(`secrets.compare_digest`, ADR-015; all `readonly=False` — Odoo 19
`auth='none'` routes are read-only by default and even debug logging
writes):

- `GET /3cx/webhook/lookup?number=&direction=` — contact lookup fired
  by 3CX at call arrival; resolves the partner via core
  `get_partner_by_number()` and returns the contact JSON 3CX maps to
  its outputs (`ContactUrl` → the partner form URL, `EntityId` → the
  partner id, phones, email). Runs under `sudo()` after the token
  check (read-only partner data, same trust level as the Asterisk
  caller-name lookups).
- `POST /3cx/webhook/report_call` — call journaling fired by 3CX at
  call end; dispatches under `connect.user_connect_webhook` and writes
  the ledger (see 3).
- `POST /3cx/webhook/create_contact` — contact creation requested from
  a 3CX client for an unmatched caller; creates the `res.partner` and
  returns the full contact JSON (single scenario, no fetch chain).

Auth: `X-Connect-Api-Key: <threecx_api_key>` header (also accepted as
`Authorization: Bearer`); all routes additionally gate on
`threecx_enabled`.

### 3. Ledger integration from the journal payload

The CRM template has **no call-id variable**, so the journal handler
builds a deterministic SID —
`3cx-<sha1(agent|number|CallStartTimeUTCMillis|call_type)>` — and runs
the standard core pipeline (`process_channel_event` +
`process_call_event`), making replays idempotent. Mapping:

| 3CX `CallType` | channel event | call status |
|---|---|---|
| `Inbound` | `technical_direction='inbound'`, `called_pbx_user` from `threecx_exten` | `completed` |
| `Missed` | same as Inbound | `no-answer` |
| `Outbound` | `technical_direction='outbound-api'`, `caller_pbx_user` from `threecx_exten` | `completed` |
| `Notanswered` | same as Outbound | `no-answer` |

Duration comes from `CallEstablishedTimeUTCMillis`/`CallEndTimeUTCMillis`
(fallback: the `hh:mm:ss` `Duration` string). The `EntityId` returned
by our own lookup (the partner id) backfills `channel.partner` when
number-based matching fails. One journal POST per call — 3CX reports
external calls only, once, at call end; there are **no live channel
states in phase 1** (calls appear in the ledger post-factum).

When the payload carries `RecordingUrl` / `Transcription` / `Summary`
(3CX V20 AI features), a `connect.recording` **reference** is created
with `skip_transcription` context: `media_url` points into the 3CX web
client (audio is not downloadable at this tier), and the 3CX-provided
transcript/summary fill the core fields directly — core OpenAI
transcription must not attempt to fetch the URL.

### 4. Click-to-call via the 3CX Web Client dial URL

There is no server-side originate API below the AI edition. The
`originate_call()` override (dispatch key `'3cx'`, ADR-031 pattern)
returns an `ir.actions.act_url` opening
`https://<pbx>/webclient/#/call?phone=<number>` — the user's own 3CX
Web Client places the call; the call lands in the ledger via the
journal webhook like any other. Two supporting changes:

- core `connect.call.redial()` now **returns** the provider action so
  URL-based providers work from the call form button (other providers
  return `True`/`None`, which buttons ignore — no behavior change);
- the phone-field widget patch (deliberately duplicated per provider,
  ADR-031) awaits `originate_call` and executes a returned action dict
  via the action service. Like the sms.composer note in ADR-032,
  co-installation keeps the last-loaded patch — acceptable because
  every patch routes through the core dispatcher.

### 5. Generated CRM template, not a hand-maintained one

The 3CX-side configuration is a single XML template rendered by Odoo
(`templates/crm_template.xml` + `string.Template` substitution of the
instance URL and API key) and downloaded from the settings form
(`/3cx/template`, `auth='user'`, admin-group check). Scenarios: contact
lookup (empty Id), `ReportCall`, `CreateContactRecordFromClient` —
built strictly on 3CX-documented predefined variables, with
`ReportCall` implemented as `PostValues`/JSON per 3CX's own template
spec. `SkipIf` gates only on the `ReportCallEnabled` parameter — NOT on
`[EntityId]` — so unmatched calls are journaled too (the ledger wants
every call, unlike CRM-contact journaling). Target: 3CX V20
(`RecordingUrl`/`Transcription`/`Summary` variables do not exist on
older releases).

### 6. Intentionally not implemented in phase 1

- Live call events, originate through the PBX, recording audio
  download, user sync — phase 2 (Call Control API + XAPI sidecar
  agent, AI edition only, separate ADR).
- `connect.message.send()` — 3CX exposes no third-party SMS surface.
- Web phone — impossible (no WSS; 3CX WebRTC closed to third parties).
- `ReportChat` journaling, email/free-text lookup scenarios, CFD
  lookups — later phases if demanded.

## Consequences

- Works on 3CX PRO and AI (V20); nothing works on Free/Basic/SMB —
  those editions have no CRM integration at all. Sales qualification
  required.
- Calls appear in the ledger only after hangup; the phone widget shows
  no live 3CX calls. This is the tier's ceiling, documented to users.
- Internal 3CX calls never reach Odoo (3CX journals external calls
  only).
- 3CX loads templates at service start and caches them; template
  changes on the 3CX side may require a service restart (3CX-side
  operational detail, documented in the admin guide).
- If 3CX ships its own Odoo template (their docs carry a "Coming Soon"
  placeholder), it would compete only with the lookup/journal part —
  not with the ledger, transcription storage, or the phase-2 deep tier.
