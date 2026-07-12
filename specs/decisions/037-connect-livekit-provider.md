# 037: connect_livekit — LiveKit provider module (self-hosted, rooms + SIP + AI agents)

## Problem

Add LiveKit as a telephony/realtime provider. LiveKit is not a carrier and
not a PBX: it is an open-source realtime stack — WebRTC SFU, a SIP bridge
(`livekit/sip`, BYO carrier trunk), recording (Egress) and a voice-AI agents
framework (LiveKit Agents). The integration must deliver three feature
levels in one module:

1. **Video rooms** — meetings created from Odoo with public guest links and
   Egress recording feeding the core transcription pipeline.
2. **SIP telephony** — inbound DID routing and click-to-call through the
   LiveKit SIP bridge with a browser web phone.
3. **AI voice agents** — a self-hosted analog of Telnyx AI Assistants
   (ADR-034) built on the LiveKit Agents framework, with function tools
   calling back into Odoo.

Deployment is self-hosted (livekit-server + redis + sip + egress + our agent
worker); LiveKit Cloud is usable with the same settings but is not the
target. The ADR number skips 035/036 — both are already used by unmerged
provider branches (infobip; bird/vonage).

## Decisions

1. **Provider model separation (ADR-031).** Config models are
   `connect.livekit.{room,trunk,number,outgoing_callerid,agent}`, fully
   owned by the module. Ledger models (`connect.call`, `connect.channel`,
   `connect.recording`, `connect.user`, `connect.settings`) are extended
   via `_inherit` with `livekit_`-prefixed fields/methods so co-installation
   with other providers keeps working. The caller-ID E.164/is_default logic
   is a deliberate full copy (no mixins); the exten/callflow machinery is
   NOT copied — LiveKit has no dialplan, routing is dispatch-rule based.

2. **Access rights: everything admin-only (owner decision).**
   `connect.group_user` gets **no** access to any connect_livekit model;
   `connect.group_admin` gets full CRUD; `connect.group_webhook` gets only
   what the webhook controllers need (read on agent/number/room, ledger
   writes come from core webhook-group rights). The web phone and the guest
   meet page work through model methods with internal sudo (the Twilio
   `get_client_token` pattern), so users need no ACLs.

3. **Odoo is the source of truth for LiveKit resources.** Trunks and
   dispatch rules are pushed to the LiveKit server on create/write/unlink
   (guarded by `livekit_auto_sync`, mirroring `telnyx_auto_sync`); the
   `sid`s of created resources are stored readonly. Agents have no remote
   copy at all — the worker pulls agent config from Odoo at dispatch time,
   so edits apply to the next call instantly.

4. **Async SDK bridging.** `livekit-api` is asyncio-only.
   `connect.settings.livekit_api_call("<service>.<method>", request)` runs
   each call in a private event loop via `asyncio.run()` — safe in threaded
   HTTP/cron workers, forbidden in the gevent websocket worker (guarded
   with a clear error). Access tokens (`AccessToken` → JWT) are pure-sync.

5. **Ledger mapping.** One LiveKit participant = one `connect.channel`
   (`sid` = participant SID, SIP participants prefer the `sip.callID`
   attribute); a room groups channels into one `connect.call` via the new
   indexed `connect.call.livekit_room_name`. Room-name prefixes encode the
   scenario: `meet-` (video meeting), `did-<number_id>-` (inbound SIP),
   `out-` (click-to-call), `ai-out-` (outbound AI call). Webhook handlers
   are idempotent upserts by sid — LiveKit may deliver events out of order.

6. **Webhook authentication.** LiveKit webhooks arrive with
   `Content-Type: application/webhook+json` and a JWT in `Authorization`
   signed with the API key/secret; they are verified with
   `livekit.api.WebhookReceiver(TokenVerifier(key, secret))`, toggled by
   `livekit_verify_webhooks` (default on). All state-changing
   `auth='public'`/`auth='none'` routes carry `readonly=False` (Odoo 19
   defaults them to the readonly cursor) and write as the shared
   `connect.user_connect_webhook` identity. Worker/uploader endpoints use
   `Authorization: Bearer <livekit_agent_token>` (the asterisk-agent
   pattern); per-agent tool webhooks use `X-Odoo-LiveKit-Token` =
   `agent.tool_token` (the Telnyx AI pattern).

7. **Recording → transcription.** Egress writes files to a shared volume;
   the uploader sidecar POSTs them to Odoo which stores them in
   `connect.recording.recording_attachment` with `source='livekit'`. The
   core transcription cron picks them up via `transcription_pending` —
   this requires the core fix making `transcribe_recording()` work from
   the attachment when `media_url` is empty (also a latent Asterisk bug).
   AI-agent conversations instead deliver a ready transcript
   (`source='livekit-ai'`, `skip_transcription=True`, Telnyx AI pattern).

8. **AI agents: plugin cascade (owner decision).** Per-agent selection of
   STT (Deepgram / OpenAI), LLM (OpenAI) and TTS (OpenAI / ElevenLabs),
   plus an OpenAI Realtime mode. Keys live in `connect.settings`
   (`deepgram_api_key`, `elevenlabs_api_key` — named without the livekit_
   prefix on purpose: they are AI vendor keys like the core
   `openai_api_key`, not LiveKit resources) and are handed to the worker
   in the agent-config payload; worker env vars act as fallback. The
   worker registers as `agent_name='connect-livekit-agent'` and is only
   dispatched explicitly (dispatch-rule `room_config.agents` for inbound,
   `AgentDispatchService.create_dispatch` for outbound).

9. **Web phone: room-per-call, token-per-join.** The browser widget joins
   LiveKit rooms with short-TTL JWTs minted by
   `connect.user.get_livekit_room_token(room_name)` — a fresh token per
   join replaces refresh flows. Click-to-call creates the room, dials the
   PSTN leg via `CreateSIPParticipant` and pushes
   `connect_livekit.call {action: 'join'}` to the user's private bus
   channel; inbound DID→user dispatch pushes `action: 'ring'`. Audio-only
   in v1; SIP registration of hardphones is impossible (livekit-sip has
   no registrar) and out of scope.

10. **Sidecar image `oduist/livekit-agent`.** One image, two commands:
    `run` (the Agents worker) and `upload-recordings` (the egress-volume
    uploader). Versioning follows the asterisk-agent policy: rebuilt only
    when a release changes `connect_livekit/deploy/agent/`; tag = short
    manifest version; multi-arch (amd64+arm64) — it runs on customer
    hardware. livekit-server/sip/egress/redis ship as pinned upstream
    images in `deploy/docker-compose.yml`.

11. **v1 scope exclusions** (deliberate): internal user↔user calls
    (meetings cover it), attended transfer, video over SIP, hardphone SIP
    registration, LiveKit Phone Numbers (US-only cloud feature), Ingress.

## Consequences

- New module `connect_livekit` (version 19.0.1.0.0), depends `connect`,
  python dep `livekit-api`.
- Core prerequisite (separate commit, own version bump): attachment-aware
  `connect.recording.transcribe_recording()`.
- Frontend: vendored pinned `livekit-client` UMD build; systray phone
  widget (Twilio layout) + a standalone public meet page (QWeb, own asset
  bundle, no website dependency).
- One LiveKit stack pairs with exactly one Odoo instance (the webhook URL
  in `livekit.yaml` is stack-global) — documented in the admin guide.
- Live verification runs in the oduflow environment with the shared
  FreeSWITCH service acting as the SIP carrier for inbound/outbound tests.
