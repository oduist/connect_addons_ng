# 036 — connect_vonage: Vonage provider module

## Status

Accepted (2026-07).

## Problem

Customers on Vonage (ex-Nexmo) need the same Connect feature set that
`connect_twilio` delivers on Twilio: inbound/outbound call tracking, IVR
callflows, browser web phone, SMS, call recordings with AI transcription.
The Vonage platform differs from Twilio in several structural ways, so a
straight port is not possible:

1. **NCCO instead of TwiML.** Call control answers are JSON arrays
   (NCCO actions), not XML documents.
2. **One Application, not per-app resources.** A single Vonage
   Application binds all webhooks (voice answer/event, messages
   inbound/status, RTC) and holds an RS256 key pair. The private key is
   returned **only at creation time**.
3. **No SIP domains / SIP endpoints.** Browser calling uses the Vonage
   Client SDK (JS) + the Users API: a JWT with `sub=<user name>` signed
   by the application private key logs the browser in; calls reach it
   via NCCO `connect` to an `app` endpoint. There is no SIP registration
   product, so the Twilio `connect.domain` model has no counterpart.
4. **Signed JWT webhooks.** With `signed_callbacks=true` Vonage sends an
   HS256 JWT (signed with the account signature secret) in the
   `Authorization` header; claims include `payload_hash` (SHA-256 of the
   body).
5. **Recording downloads require JWT auth.** `recording_url` cannot be
   fetched with a plain GET, so the core transcription pipeline (which
   downloads `media_url` unauthenticated) cannot be used as-is.
6. **No ParentCallSid.** Legs of one call share a `conversation_uuid`;
   the parent leg must be resolved heuristically.

## Options considered

- **TeXML-style compatibility layer** — Vonage has no Twilio-XML
  emulation (unlike Telnyx), not applicable.
- **Event-driven call control via REST only** (as `connect_infobip`,
  ADR-035) — possible, but Vonage's native model is answer-webhook +
  NCCO, which matches the existing `connect_twilio` render architecture
  almost 1:1; using it keeps the port small and the callflow engine
  shared in spirit.
- **Chosen: NCCO render architecture mirroring connect_twilio**, with
  provider-specific adaptations listed below.

## Decision

New addon `connect_vonage` (depends: `connect`, external python dep:
`vonage` v4 SDK). Key decisions:

- **`connect.ncco` replaces `connect.twiml`**: same code_type triad
  (`ncco` JSON with jinja2, `nccopy` python, `model_method`), but
  `render()` returns a Python list serialized by the controllers with
  `Content-Type: application/json`. NCCO apps are pure server-side
  content — unlike TwiML apps they need no Vonage-side resource sync.
- **Application lifecycle in settings**: `connect.settings.sync()`
  creates the Vonage Application (voice + messages v1 + rtc
  capabilities, `signed_callbacks=true`, webhook URLs built from
  `connect.api_url`) when `vonage_application_id` is empty, storing the
  returned application id and private key; otherwise it updates the
  existing application's URLs. Re-using a pre-existing application
  requires pasting its private key manually (protected settings field).
- **Webhooks** under `/vonage/webhook/*`: `answer`, `event`,
  `recording`, `vm_recording`, `ncco/<id>`,
  `<model>/call_action/<id>`, `callflow/<id>/input`, `message`,
  `message_status`, `rtc`. All are `auth='public'`, `csrf=False`,
  `readonly=False` (Odoo 19 requirement for writing public routes),
  validate the JWT (`vonage_jwt.verify_signature` + `payload_hash`
  check) and execute as `connect.user_connect_webhook`.
- **Leg correlation**: `connect.channel.sid` = per-leg `uuid`; new
  indexed `conversation_uuid` field; when an event's leg is new and
  Vonage supplied no parent, the earliest channel with the same
  `conversation_uuid` becomes `parent_sid`.
- **Status map** (Vonage → core/Twilio vocabulary): started→initiated,
  ringing→ringing, answered/human/machine→in-progress,
  completed→completed, busy→busy, cancelled→canceled,
  timeout/unanswered→no-answer, rejected/failed→failed.
- **User callflow chaining** keeps the core `connect.user_callflow` /
  `user_callflow_call` engine: each step is one NCCO; `connect` actions
  carry `eventType=synchronous` with
  `/vonage/webhook/connect.user/call_action/<id>` so failure statuses
  (timeout/unanswered/busy/failed/rejected/cancelled) return the next
  step's NCCO (e.g. voicemail) while other events return an empty body
  (continue). Voicemail is stored as a `connect.recording` with
  `source='voicemail'` (see recording decision) instead of
  `call.voicemail_url`, because voicemail media also requires JWT auth.
- **Recordings**: the record event handler creates the
  `connect.recording` with `vonage_recording_url` set and `media_url`
  left empty (context `skip_transcription`). Recording UUIDs are
  idempotency keys, and a cron
  (`_cron_download_vonage_recordings`) downloads via
  `client.voice.download_recording()` (JWT) into
  `recording_attachment` and only then flags `transcription_pending`.
  `transcribe_recording()` is overridden to feed Whisper from the
  attachment when there is no `media_url`.
- **Web phone**: Vonage Client SDK JS (vendored UMD bundle
  `vonageClientSDK.min.js`) + Users API. `connect.user` gets `username`
  (unique, alnum) and `vonage_user_id`; create/unlink provision/delete
  the Vonage user when `vonage_auto_sync` is on.
  `get_client_token()` mints an RS256 JWT (`sub=username`, 1h TTL,
  standard ACL paths) with `vonage_jwt.JwtClient`. Client-originated
  calls hit the application answer_url with `from_user`; the handler
  builds an outbound `connect` NCCO and pre-creates the channel.
  Installation backfills missing usernames from sanitized Odoo logins
  before restoring the database `NOT NULL` constraint.
- **Click-to-call** (`originate_call`): `voice.create_call` to the
  agent's `app` endpoint with an inline NCCO that records (optional)
  and connects to the destination number; the channel is pre-created
  with `technical_direction='outbound-api'`.
- **Numbers**: `connect.number.sync()` imports owned numbers
  (`numbers.list_owned_numbers`) and links each to the application
  (`numbers.update_number(app_id=...)`). Numbers are stored E.164 with
  a leading `+` (Vonage APIs use bare digits; helpers convert).
  `connect.outgoing_callerid` is seeded from owned numbers
  (`callerid_type='number'`) — Vonage has no verified-caller-id API.
- **Messages**: v1 ships SMS via the Messages API
  (`messages.send(Sms(...))`); inbound and delivery receipts arrive on
  the application `inbound_url`/`status_url`. WhatsApp senders,
  templates and media composers are deferred to v1.1.
- **Callflow IVR**: `talk` (bargeIn) + `input` NCCO actions; the input
  `eventUrl` posts to `/vonage/webhook/callflow/<id>/input`. Multiple
  `ring_users` ring **sequentially** (Vonage `connect` takes a single
  endpoint; the NCCO advances to the next action on failure) — a
  documented difference from Twilio's simultaneous `<Dial>`.

## Known limitations / follow-ups

- Simultaneous ring is not possible with plain NCCO `connect`.
- Call transfer (core transfer wizard) is not implemented in v1.
- WhatsApp/MMS sending, machine detection, call price fetching
  (`CallInfo.price`) are deferred.
- The Client SDK browser integration needs a live verification pass
  (session refresh, audio handling) — same caveat as ADR-035 v1.
