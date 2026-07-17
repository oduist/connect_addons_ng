# Connect LiveKit Module Specification

## Module Info

- **Name:** Oduist Connect LiveKit
- **Technical:** `connect_livekit`
- **Version:** 19.0.1.0.0
- **Depends:** `connect`
- **Python deps:** `livekit-api`
- **Application:** False
- **License:** Other proprietary

## Overview

The `connect_livekit` module integrates a **self-hosted LiveKit stack**
(WebRTC SFU + SIP bridge + Egress recording + Agents framework) with the
Connect platform (ADR-036). It delivers three feature levels:

1. **Video rooms** (`connect.livekit.room`) — meetings created from Odoo,
   public guest links (`/livekit/meet/<guest_token>`), Egress recording
   into `connect.recording` and the core transcription pipeline.
2. **SIP telephony** — DID routing via LiveKit dispatch rules
   (`connect.livekit.number` over `connect.livekit.trunk`), click-to-call
   via `CreateSIPParticipant`, a browser web phone joining rooms with
   short-TTL JWTs.
3. **AI voice agents** (`connect.livekit.agent`) — served by the
   `oduist/livekit-agent` sidecar worker (LiveKit Agents framework) with a
   per-agent STT/LLM/TTS plugin cascade (Deepgram/OpenAI/ElevenLabs) or
   OpenAI Realtime, function tools calling back into Odoo, transcripts
   stored as `connect.recording` with `source='livekit-ai'`.

Everything contributed to the **shared** ledger models carries a
`livekit_` prefix. LiveKit has no dialplan: there are no exten/callflow
models; inbound routing is dispatch-rule based. The caller-ID
E.164/is_default logic is a deliberate copy of the other providers
(ADR-031 — no mixins).

**Access rights (owner decision, ADR-036):** all module models are
admin-only. `connect.group_user` has no ACLs; browser features go through
model methods with internal sudo. `connect.group_webhook` gets read-only
rows needed by the webhook controllers.

Room-name prefixes encode the scenario and drive the ledger mapping:
`meet-` (meeting), `did-<number_id>-` (inbound SIP), `out-`
(click-to-call), `ai-out-` (outbound AI call). One participant = one
`connect.channel` (sid = participant SID / `sip.callID`), one room = one
`connect.call` (`livekit_room_name`, indexed).

### v1 scope exclusions (ADR-036)

Internal user↔user calls, attended transfer, video over SIP, hardphone
SIP registration (livekit-sip has no registrar), LiveKit Cloud phone
numbers, Ingress.

---

## Models (connect_livekit/models/)

### settings.py — `connect.settings` (inherit)

Fields: `livekit_ws_url`, `livekit_api_url` (optional, derived from WS URL
when empty), `livekit_api_key` + `livekit_api_secret` (erp_manager groups,
secret masked via `display_livekit_api_secret`), `livekit_sip_uri` (info
for carrier-side trunk config), `livekit_verify_webhooks` (default on),
`livekit_auto_sync` (default on), `livekit_agent_token` (Bearer secret of
the worker/uploader sidecar + `action_generate_livekit_agent_token()`),
`deepgram_api_key`, `elevenlabs_api_key` (masked AI vendor keys, no
livekit_ prefix on purpose).

Methods: `livekit_api_call("<service>.<method>", request)` — sync wrapper
running one asyncio loop per call around `livekit.api.LiveKitAPI`
(threaded workers only); `livekit_create_token(identity, ...)` — sync JWT
mint; `livekit_sync()` — connectivity check + push of trunk/number/
callerid resources; `originate_call()` override with the standard
`_get_originate_provider(user) != 'livekit'` fall-through. Click-to-call
creates room `out-…`, creates the ledger call before notifying the browser,
dials the PSTN leg with `CreateSIPParticipant`, links the returned SIP call
id channel to that call, then pushes `connect_livekit.call` over the bus.

### user.py — `connect.user` (inherit)

`originate_provider` += `('livekit', 'LiveKit')`;
`livekit_client_enabled`, `livekit_exten_number` (unique, in
`_pbx_number_fields()`), `livekit_outgoing_callerid` (M2o).
`get_livekit_phone_config()` (systray bootstrap: enabled/ws_url/identity)
and `get_livekit_room_token(room_name)` (join authorization + short-TTL
token, sudo inside). Browser identity format: `user-<connect_user_id>`.

### room.py — `connect.livekit.room`

`name`, `room_name` (`meet-<uuid8>`, unique, readonly), `sid`, `state`
(draft/active/finished), `user` (organizer), `partner`, `ref` (Reference),
`guest_token` (urlsafe, unguessable public link), `public_url` (compute),
`record`, `egress_sid`, `empty_timeout`, `max_participants`, `call` (M2o
ledger link). Actions: `action_join`, `action_start_recording` /
`action_stop_recording` (RoomComposite Egress, audio OGG by default,
filepath `/out/{room_name}-{time}` so the uploader sees it),
`action_close` (DeleteRoom). `_ensure_livekit_room()` creates the LiveKit
room on first join.

### trunk.py — `connect.livekit.trunk`

Inbound: `inbound_trunk_sid` (readonly), `inbound_addresses`,
`inbound_auth_username/password`, `krisp_enabled`. Outbound:
`outbound_trunk_sid` (readonly), `outbound_address`, `outbound_transport`,
`outbound_auth_username/password`. `sync()` + auto-push on write
(`livekit_auto_sync`, `skip_livekit_sync` context guard).

### number.py — `connect.livekit.number`

`phone_number` (E.164, unique), `friendly_name`, `trunk` (M2o, required),
`destination` ∈ user/agent/room + matching M2o (write() nulls the
non-selected ones), `dispatch_rule_sid` (readonly). Dispatch rules:
user → Individual rule (`room_prefix='did-<id>-'`) + bus ring;
agent → Individual rule with `room_config.agents=[RoomAgentDispatch(
agent_name='connect-livekit-agent', metadata={'agent_id': id})]`;
room → Direct rule to `room.room_name`.

### outgoing_callerid.py — `connect.livekit.outgoing_callerid`

Deliberate structural copy of the Telnyx caller-ID model (E.164
constraint, unique number, `is_default` + `_reset_default`), plus `trunk`
M2o (which outbound trunk carries the number) and `callerid_users` O2m.

### agent.py — `connect.livekit.agent`

`name`, `description`, `active`, `instructions`, `greeting`, `mode`
(pipeline/realtime), `stt_provider` (deepgram/openai) + `stt_model`,
`llm_model`, `tts_provider` (openai/elevenlabs) + `tts_model`, `voice`,
`language`, `time_limit_secs` (30..14400), `record_calls`,
`enable_contact_tools`, `enable_crm_tools`, `enable_helpdesk_tools`,
`tool_token` (secret per agent, `action_rotate_tool_token()`).
`execute_tool(tool_name, payload, channel_sid)` — allowlisted
lookup_contact / add_contact_note / upsert_crm_lead /
upsert_helpdesk_ticket (Telnyx AI adaptation).
`_agent_config_payload()` — worker contract (config + tool_token +
webhook base + AI keys). `action_call_with_agent()` opens the outbound
wizard.

### call.py / channel.py / recording.py — ledger (inherit)

`connect.call.livekit_room_name` (indexed), `livekit_agent` (M2o);
`on_livekit_webhook(event)` — idempotent dispatcher of room_started /
participant_joined / participant_left / room_finished / egress_*.
`connect.channel.livekit_process_event()` maps participants to
`process_channel_event()` params. `connect.recording`: egress recordings
(`source='livekit'`, file arrives from the uploader, transcription via
core `transcription_pending`), AI transcripts
(`livekit_apply_agent_transcript`, `source='livekit-ai'`,
`skip_transcription=True`).

---

## Controllers (connect_livekit/controllers/)

| Route | Auth | Purpose |
|---|---|---|
| `POST /livekit/webhook` | public, readonly=False | WebhookReceiver JWT verification → `on_livekit_webhook` as webhook user |
| `POST /livekit/webhook/agent/<id>/tool/<name>` | public, readonly=False | `X-Odoo-LiveKit-Token` == `agent.tool_token` → `execute_tool` (64KB cap) |
| `POST /livekit/webhook/agent/<id>/transcript` | public, readonly=False | same token → `livekit_apply_agent_transcript` |
| `PUT /livekit/webhook/recording/<fname>` | none, readonly=False | Bearer `livekit_agent_token` → `recording_attachment` |
| `GET /livekit/api/agent_config` | none | Bearer → `_agent_config_payload()` |
| `POST /livekit/api/heartbeat` | none, readonly=False | Bearer → `livekit_worker_last_seen` marker; the worker posts it at startup and on every dispatched job |
| `GET /livekit/meet/<guest_token>` | public | QWeb meet page |
| `POST /livekit/meet/<guest_token>/join` | public, readonly=False | guest/internal join token |

## Frontend (connect_livekit/static/src/)

Vendored pinned `livekit-client` UMD build in `lib/`. Web phone: Twilio
main.js layout (service + systray + main_components gated by
`get_livekit_phone_config`), bus channel `connect_livekit.call`
(`join`/`ring` actions), lazy SDK load, fresh token per join. Meet page:
standalone asset bundle, name entry → join → participant tiles,
mute/camera/leave, recording indicator.

## Deploy (connect_livekit/deploy/)

`docker-compose.yml`: pinned `livekit/livekit-server`, `redis:7-alpine`,
`livekit/sip`, `livekit/egress` (shared egress-out volume),
`oduist/livekit-agent` (`run` + `upload-recordings` commands), optional
TLS proxy. `livekit.yaml` carries the webhook URL of the paired Odoo
(one stack = one Odoo). Sidecar image versioning: rebuilt only when a
release changes `deploy/agent/`; tag = short manifest version;
multi-arch amd64+arm64.

## Security

All `connect.livekit.*` models: admin full CRUD, webhook read where the
controllers need it (agent, number, room), **no user-group rows**
(ADR-036 owner decision). Secrets (`livekit_api_secret`, AI keys,
`livekit_agent_token`, `tool_token`) never reach the webhook group.
