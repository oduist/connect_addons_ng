# connect_vonage — Vonage Integration Module Specification

Vonage (ex-Nexmo) provider module for Oduist Connect. Implements the core
provider contract (ADR-036) on top of the official `vonage` v4 Python SDK:
NCCO-driven voice, Client SDK web phone, Messages API SMS, recordings with
JWT-authenticated download.

## Dependencies

- Odoo module: `connect`
- Python: `vonage` (v4 metapackage: vonage-voice, vonage-messages,
  vonage-application, vonage-users, vonage-numbers, vonage-jwt, ...)
- Frontend: vendored `@vonage/client-sdk` UMD bundle
  (`static/src/lib/vonageClientSDK.min.js`)

## Models

### connect.settings (extension)

| Field | Notes |
|---|---|
| `vonage_api_key` / `vonage_api_secret` | Basic auth (account, numbers). Secret is protected (`display_vonage_api_secret` masked twin) |
| `vonage_application_id` | Set by sync on application creation, or manually to reuse an existing application |
| `vonage_private_key` | RS256 application key (protected, masked twin). Returned by Vonage **only at application creation** |
| `vonage_signature_secret` | HS256 secret for signed webhook JWTs (protected, masked twin) |
| `vonage_region` | Optional voice region (`na-east`, `eu-west`, ...) |
| `vonage_auto_sync` | Push CRUD to Vonage (users) |
| `vonage_verify_requests` | Validate webhook JWTs (default on) |
| `vonage_balance` | Readonly, `get_vonage_balance()` button |

Methods: `get_client()` (SDK `Vonage` with both auth modes),
`get_jwt_client()` (JwtClient for web phone tokens),
`get_vonage_webhook_url(path)`, `sync()` (application + users + numbers +
callerids), `sync_vonage_application()`, `vonage_create_call(payload)`
(raw `POST /v1/calls` — the SDK's CreateCallRequest cannot dial `app`
endpoints), `originate_call()` (click-to-call: agent app endpoint first,
inline NCCO record + connect to the destination).

### connect.ncco (new)

NCCO application, the counterpart of `connect.twiml`. Pure server-side
content (no Vonage resource): `code_type` in `ncco` (JSON, jinja2),
`nccopy` (python code assigning the `ncco` list), `model_method`.
`render(request, params)` returns a Python list; controllers serialize
it as `application/json`. ACL: admin CRUD, connect user read, webhook
read.

### connect.channel (extension)

- `conversation_uuid` (indexed) — Vonage sends no parent leg id; the
  earliest channel with the same conversation_uuid becomes `parent_sid`.
- `on_voice_event(params)` → `_map_vonage_params()` →
  `process_channel_event()`. Status map: started→initiated,
  ringing→ringing, answered/human/machine→in-progress,
  completed→completed, busy→busy, cancelled→canceled,
  timeout/unanswered→no-answer, rejected/failed→failed. App legs are
  normalized to `client:<username>@vonage` URIs. Updates never
  overwrite the pre-created `technical_direction` (originate legs).

### connect.call (extension)

`on_voice_event(params)`: channel adapter + `process_call_event()` with
error data from failed/rejected statuses; caller notification on
outgoing errors.

### connect.user (extension)

- `username` (required, unique, alnum), `vonage_user_id`,
  `client_enabled`, `client_ring_timeout`.
- Users API lifecycle: create/unlink provision/delete the Vonage user
  when `vonage_auto_sync` is on; `sync_vonage_users()` backfills.
- `get_user_by_uri()` resolves `client:<username>@...` URIs.
- NCCO callflow engine (mirrors connect_twilio): `render()` walks
  `connect.user_callflow` by prio using `connect.user_callflow_call`
  tracking; `render_client()` emits `connect` to the `app` endpoint with
  `eventType=synchronous` and eventUrl
  `/vonage/webhook/connect.user/call_action/<id>`; `render_voicemail()`
  emits talk + record (eventUrl `vm_recording`). `on_call_action()`
  records the leg event and returns the next step's NCCO only for
  failure statuses (timeout/unanswered/busy/failed/rejected/cancelled).
- `on_client_call(params)`: answer webhook handler for web phone
  originated calls (`from_user`) — pre-creates the `outbound-api`
  channel and returns the outbound NCCO.
- `get_client_token()`: Client SDK JWT (`sub=username`, 1h TTL, standard
  ACL paths) for the web phone.

### connect.number (extension)

`country`, `features`, `ncco` destination (selection_add). `sync()`
imports owned numbers (stored `+E.164`) and links them to the
application (`numbers.update_number(app_id=...)`). `route_call(params)`
creates the inbound channel (answer arrives before status events) and
renders the destination.

### connect.callflow (extension)

IVR via `talk` (bargeIn) + `input` NCCO actions; input eventUrl
`/vonage/webhook/callflow/<id>/input` → `gather_action()` (dtmf digits /
speech results). `ring_users` ring **sequentially** (one endpoint per
`connect`; NCCO advances on failure) with voicemail fallback.
`gather_input_type` adds speech / dtmf+speech.

### connect.recording (extension)

- `vonage_recording_url`, `vonage_downloaded`. Vonage recording URLs
  need JWT auth, so `media_url` is never set.
- `on_recording_event(params)` creates the record
  (`skip_transcription`), resolves the channel by conversation_uuid,
  computes duration from start/end and attempts an inline download;
  `_cron_download_vonage_recordings` (every 2 min) retries into
  `recording_attachment`, then flags `transcription_pending`.
- `get_transcript()` / `transcribe_recording()` overridden to feed
  Whisper from the attachment. Voicemail recordings are stored with
  `source='voicemail'` (no `call.voicemail_url`).

### connect.message (extension)

- `send()` — Messages API SMS (`messages.send(Sms(...))`), chatter
  post, `message_sid` = message_uuid. WhatsApp send deferred to v1.1.
- `receive()` — inbound webhook mapping (channel sms/whatsapp/mms,
  media object per message_type), partner match, threading
  (whatsapp `context.message_uuid` or last message), destination via
  `connect.message_configuration`, chatter.
- `update_message_status()` — delivery receipts, errors on
  rejected/undeliverable.

### connect.exten / connect.outgoing_callerid (extensions)

`connect.ncco` as exten destination + JSON dialplan preview; caller ids
seeded from owned numbers (Vonage has no verified-caller-id API).

## Controllers (`/vonage/webhook/*`)

All `type='http'`, `auth='public'`, `csrf=False`, `readonly=False`,
executed as `connect.user_connect_webhook` after JWT validation
(`Authorization: Bearer` HS256 against `vonage_signature_secret` +
`payload_hash` SHA-256 body check; disabled by
`vonage_verify_requests=False`).

| Route | Purpose | Returns |
|---|---|---|
| `answer` (GET/POST) | Inbound number call → `number.route_call`; web phone call (`from_user`) → `user.on_client_call` | NCCO JSON |
| `event` | Voice leg status events → `call.on_voice_event` | OK |
| `recording` / `vm_recording` | Record action events → recording create + download | OK |
| `ncco/<id>` | Render an NCCO app | NCCO JSON |
| `<model>/call_action/<id>` | Synchronous connect events (whitelist: connect.user, connect.callflow) | NCCO JSON or 204 |
| `callflow/<id>/input` | IVR input results | NCCO JSON |
| `message` / `message_status` | Messages API inbound / DLR | OK |
| `rtc` | RTC events (log only) | OK |

## Web phone

`static/src/` mirrors the connect_twilio widget tree; the device layer
is a `VonageSession` adapter over the Vonage Client SDK
(`createSession(token)`, `serverCall({to})`, `callInvite`/`callHangup`/
`legStatusUpdate` events, `answer/reject/hangup/mute/sendDTMF`). Token
refresh at ~80% of the 1h TTL via `get_client_token`
(`refreshSession` when available, else session re-create). Remote audio
is handled by the SDK. No auto-answer for click-to-call yet (the agent
answers the ringing web phone).

## Security

- New model ACLs: see `security/access_rules.xml` (connect.ncco).
- Webhook secrets are read via `sudo()` in controllers only; settings
  fields are `groups="base.group_erp_manager"` with masked display
  twins.

## Known limitations (v1)

- Simultaneous ring, call transfer, WhatsApp/MMS send, machine
  detection, call price fetching — deferred (ADR-036).
- Client SDK browser integration pending live verification.
