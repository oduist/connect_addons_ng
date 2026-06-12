# 025 — Asterisk provider via a thin sidecar agent (`connect_asterisk`)

## Status

Accepted

## Context

The product ships two providers on top of the technology-agnostic `connect`
core: `connect_twilio` (cloud REST API + webhooks) and `connect_freeswitch`
(self-hosted, XML-RPC control + direct HTTP callbacks from FreeSWITCH).
We are adding Asterisk support, ported from the legacy `asterisk_plus`
product (Odoo 10–17, ~4000 lines core + JsSIP softphone module).

Asterisk differs from both existing providers in one critical way: its
native eventing interface (AMI) is a persistent TCP socket, and Asterisk
has no built-in way to POST call events or CDRs over HTTP the way
FreeSWITCH's `mod_xml_cdr` does. Odoo workers cannot hold a persistent
AMI connection. The legacy product solved this with a heavyweight
external "OdooPBX Agent" (AMI + FastAGI + HTTPS RPC with `{fun, args,
kwargs}` job dispatch, async callbacks via `res_model`/`res_method`
round-trips, and a DB-driven `asterisk_plus.event` registry deciding
which AMI events call which Odoo methods).

The target market is **existing customer Asterisk installations**
(FreePBX, Issabel, plain Asterisk 13–21). We do not ship an Asterisk
image; inbound routing stays in the customer's dialplan.

## Decision

### 1. Thin sidecar agent instead of the OdooPBX Agent port

A new Docker service `oduist/asterisk-agent`
(`connect_asterisk/deploy/agent/`) modeled on the firewall service
(`connect_freeswitch/deploy/firewall/`, ADR-014/015/017). The agent:

- holds the persistent AMI connection (hand-rolled asyncio client in the
  style of the firewall's `esl.py`; `panoramisk` rejected as
  effectively unmaintained);
- normalizes a **fixed allowlist** of AMI events (`Newchannel`,
  `Newstate` Up, `Hangup`, `NewConnectedLine`, `OriginateResponse`
  Failure, `VarSet MIXMONITOR_FILENAME`) into a stable JSON schema and
  POSTs them in batches to `/asterisk/webhook/events`;
- uploads finished call recordings to
  `/asterisk/webhook/recording/<uniqueid>.<ext>`;
- exposes a small HTTP API (`/originate`, `/ami_action`, `/sync`,
  `/healthz`) for Odoo-initiated actions — synchronous request/response,
  no async job callbacks.

The legacy `asterisk_plus.event` registry is **dropped**: dispatch is a
hardcoded `EVENT_HANDLERS` map in the Odoo webhook controller, and the
event filter the agent applies is served from `/asterisk/api/config`.
No business logic lives in the agent: user/partner/direction resolution
happens in Odoo via the core `connect.channel.process_channel_event` /
`connect.call.process_call_event` pipeline.

### 2. Single server on `connect.settings`

No port of the multi-server `asterisk_plus.server` model. All connection
fields live on the `connect.settings` singleton with the `asterisk_`
prefix, presented in an "Asterisk" notebook tab — exactly how
`connect_freeswitch` configures its single server. The legacy
`agent_token` + `security_token` pair collapses into one shared secret
`asterisk_agent_token`.

### 3. Symmetric Bearer auth; webhook user for event processing

Both directions authenticate with `Authorization: Bearer
<asterisk_agent_token>` compared via `secrets.compare_digest`
(ADR-015 pattern). Unlike the firewall controllers (bare `sudo()`),
the event and recording webhooks dispatch under
`with_user(connect.user_connect_webhook)`: the target models
(`connect.channel`, `connect.call`, `connect.recording`) already carry
webhook-group ACLs in core, so the webhook-user pattern bounds the
blast radius of a leaked token at no cost. Pull-style bootstrap routes
(`/asterisk/api/config`, `sip_peers`, caller-name lookups) keep the
firewall-style Bearer + `sudo()` because they only read admin-only
settings/templates. The legacy IP-allowlist (`permit_ip_addresses`)
is replaced by the Bearer token.

### 4. Recordings are pushed by the agent

The agent tracks `MIXMONITOR_FILENAME` per `Uniqueid`, waits for the
file to stabilize after `Hangup`, and PUTs it to the recording webhook
(mirroring the FreeSWITCH `record_session` upload path). Odoo links it
to the channel/call with the same orphan-tolerant logic as
`connect_freeswitch`; core handles transcription. A pull fallback
(`POST {agent}/api/recording/fetch`) backs a manual re-fetch button.
Voicemail (MiniVM) is deferred.

### 5. Softphone: JsSIP direct to the customer's Asterisk

The JsSIP softphone from `asterisk_plus_phone` is folded into
`connect_asterisk`. Component skeleton follows the Odoo-19 OWL2 phone
widget of `connect_twilio` (already wired to core models:
`connect.favorite`, `connect.call.get_widget_calls`); only the
transport layer is JsSIP over WSS, registering directly against the
customer's Asterisk (`asterisk_websocket_url`) with per-endpoint SIP
credentials. The agent is not involved in media or SIP signaling.

### 6. Reachability asymmetry (recorded, partially deferred)

The firewall precedent and the legacy agent both assume Odoo can reach
the agent over HTTP. That holds for on-prem and LAN topologies but not
for cloud-Odoo + NATed customer PBX. Phase 1 implements direct HTTP
only (originate and AMI actions fail with a clear error when the agent
is unreachable). A polling job-queue command channel (agent pulls
queued commands from Odoo, outbound-only) is the planned phase-2
fallback; the webhook/event direction is already outbound-only and
unaffected.

### 7. Intentionally not implemented in phase 1

- `connect.message.send()` — no SMS transport on plain Asterisk.
- `connect.number.route_call()` — inbound DID routing stays in the
  customer's dialplan; `connect.number` records remain available for
  labeling and the `get_user_data_by_did` dialplan-assist lookup.
- Multi-server, call spy/whisper/barge, tags, MiniVM voicemail,
  retention crons — candidates for later phases.

## Consequences

- The agent is stateless apart from an in-memory channel registry and a
  small JSON state file for pending recording uploads; it can be
  restarted at any time and heals via a periodic `CoreShowChannels`
  reconciliation that emits synthetic hangups for missed events.
- Customers only need an AMI user (`read = call,dialplan,user`,
  `write = originate,call,reporting`) and, for recordings, a volume
  mount of the monitor directory — no dialplan changes.
- Call/channel statuses use the core (Twilio-style) vocabulary
  (`ringing`, `in-progress`, `completed`, `busy`, `no-answer`,
  `canceled`, `failed`); Q.850 hangup causes are mapped in
  `connect_asterisk`, the legacy `noanswer/answered/ended` vocabulary
  disappears.
- The `asterisk_plus` satellite modules (crm, helpdesk, hr, …) are not
  ported; their role belongs to future platform-agnostic `connect_*`
  modules built on the core models.
