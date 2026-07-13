# ADR-036: connect_infobip provider module (event-driven voice, full messaging)

## Problem

We need an Infobip integration with the same product surface as
connect_twilio: click-to-call, inbound routing to users, a browser web
phone, the shared call/message ledger, recordings with OpenAI
transcription, SMS and WhatsApp messaging. Per ADR-031 it must be a
standalone module owning its `connect.infobip.*` config models and
extending the shared ledger models with `infobip_`-prefixed
fields/methods, co-installable with the other providers.

Infobip differs from Twilio/Telnyx in ways that break the established
"webhook in → XML out" template:

- **No TwiML/TeXML analog.** The Calls API is purely event-driven:
  Infobip POSTs events (`CALL_RECEIVED`, `CALL_ESTABLISHED`,
  `CALL_FINISHED`, `DIALOG_*`, `SAY_FINISHED`, ...) and the integration
  answers with REST actions on call legs (`/calls/1/calls/{id}/say`,
  `/calls/1/dialogs`, ...). There is no markup document to render.
- **No webhook signatures.** No `X-Twilio-Signature`/Ed25519 analog;
  the documented webhook security is HTTPS plus Basic Auth configured
  on the Infobip side.
- **No per-user SIP.** SIP credentials exist only at trunk level; the
  per-agent softphone model is per-user WebRTC identities with tokens
  minted via `POST /webrtc/1/token` (JS SDK: npm `infobip-rtc`).
- **The official Python SDK does not cover the Voice/Calls or Numbers
  APIs** and is community-maintained.
- **The API host is per-account** (`https://{xxx}.api.infobip.com`).

## Decisions

1. **Plain-`requests` HTTP client, no SDK.** A single
   `connect.settings.infobip_api_request(method, path, payload, params)`
   helper (plus a `_raw` variant returning bytes for recording
   downloads) sends `Authorization: App {api_key}` against the
   configured `infobip_base_url`. Errors surface the
   `requestError.serviceException.text` envelope; the API key never
   appears in error messages or logs. No `external_dependencies`.

2. **Personalized base URL is configuration.** `infobip_base_url` is a
   required settings field next to the API key; nothing is hardcoded.

3. **Webhook auth = shared token, fail-closed.**
   `infobip_webhook_token` (auto-generated `secrets.token_urlsafe(32)`)
   is embedded as `?token=` into every webhook URL the admin configures
   on the Infobip side; controllers also accept it as the Basic Auth
   password (Infobip forwarding profiles support Basic Auth). The check
   is a constant-time comparison ported from
   `connect_freeswitch/controllers/token_auth.py`; requests with no
   valid token are rejected with a uniform 401, and a missing
   configured token rejects everything (fail-closed, ADR-025).
   `infobip_verify_requests` (default on) is the escape hatch.

4. **Voice = event dispatcher + platform-side timers.** All voice
   webhooks funnel into `connect.call.on_infobip_voice_event(event,
   kind)`. A call leg maps to `connect.channel` keyed by
   `sid = callId`; `parent_sid` does not exist at Infobip and is
   synthesized by us, duplicated into the legs' `customData` together
   with `caller/called_pbx_user_id` and `technical_direction` so
   webhook-created rows stay fully correlated under races. Two legs are
   bridged with a Dialog (`POST /calls/1/dialogs` with
   `childCallRequest`); ring timeouts are the platform's
   `connectTimeout` — no Odoo-side timers. Ring progress lives on the
   parent channel (`infobip_route_step` over the user's
   `connect.infobip.user_callflow` steps).

5. **Webhook idempotency.** Handlers serialize per `callId` with
   `pg_advisory_xact_lock(hashtext(callId))`, never downgrade a
   terminal channel status, drop stale status events by event
   timestamp, and always ACK 200 (errors are logged, not raised) so
   Infobip does not retry-storm.

6. **Recordings are attachment-first.** Recording files require an
   authorized download (`GET /calls/1/recordings/files/{fileId}` with
   the App key), so `media_url` cannot be handed to the browser or the
   transcription cron. Recording events create `connect.recording`
   rows flagged `infobip_download_pending`; a cron downloads the bytes
   into `recording_attachment`. One small provider-agnostic core seam:
   `connect.recording.transcribe_recording()` prefers
   `recording_attachment` over downloading `media_url` (and
   `get_transcript()` accepts either). Everything downstream
   (playback widget, transcription, proxy) already supports
   attachments.

7. **Web phone dials through the platform.** The browser SDK calls
   `callApplication(callsConfigurationId, {customData: {dialed_number}})`
   so every web-phone call arrives as `CALL_RECEIVED` and Odoo stays in
   the routing loop and on the ledger (same philosophy as Telnyx's SIP
   subdomain routing, ADR-032). A settings flag
   `infobip_webphone_via_rest` switches the widget to the REST
   originate path if `callApplication`/customData round-trip is not
   available on the account.

8. **SMS delivery reports via per-send `notifyUrl`** — no
   account-level DLR subscription management. Inbound SMS uses the
   Numbers API per-number "forward to HTTP" action, pushed
   (best-effort) on number sync. WhatsApp inbound and DLR forwarding
   are configured on the Infobip side to the same webhook URLs (shown
   in the settings form).

9. **`infobip_setup_webhooks()` is best-effort.** It auto-creates the
   "Odoo Connect" Calls configuration when possible and always surfaces
   the exact webhook URLs with manual portal instructions; account
   variants (classic vs CPaaS-X) make subscription auto-provisioning
   unreliable, so admin-entered IDs are authoritative and never
   overwritten.

10. **Voice v1 scope: direct routing only.** `connect.infobip.number`
    routes to a user (WebRTC client and/or external phone via
    prioritized `user_callflow` steps) or to an external number. There
    are NO callflow/IVR models in v1; `connect.infobip.exten` exists
    with `dst` limited to `connect.user`. Ring-exhausted/unconfigured
    calls get a TTS apology (`say`) and hangup; recorded voicemail is
    deferred.

11. **Deliberately duplicated blocks now span four modules.** The exten
    dst-Reference mechanics and the caller-ID E.164/is_default logic
    are copied into connect_infobip per ADR-031 (no mixins). The
    callflow language list is NOT copied (no IVR in v1). A fix in one
    copy must be applied to connect_twilio, connect_freeswitch,
    connect_telnyx AND connect_infobip in the same commit.

12. **Messaging co-installation limitation restated.**
    `connect.message.send()`, `_compute_direction()` and the
    `sms.composer` inherit follow the ADR-032 pattern: with several
    messaging providers installed the last-loaded module wins. A core
    dispatcher hook remains deferred.

13. **Access matrix mirrors Twilio/Telnyx.** connect.group_user: read
    on exten/number/outgoing_callerid/user_callflow/whatsapp_sender/
    whatsapp_template, CRUD on composers; connect.group_admin: full
    CRUD; connect.group_webhook: read on exten/number/
    outgoing_callerid/whatsapp_sender; message_configuration is
    admin-only.

14. **v1 exclusions:** IVR/callflows, recorded voicemail, RCS, Viber,
    number purchasing, call price fetch (Infobip exposes no per-call
    price on the call resource; CDR/Analyze availability is
    account-dependent), parallel ring within a step, conferences and
    transfers.

## Consequences

- Voice logic is stateful Odoo code instead of rendered XML; the
  webhook controller is a hard dependency of ringing calls, so the
  idempotency/locking rules in Decision 5 are load-bearing.
- Webhook trust relies entirely on the token + HTTPS (Decision 3);
  operators must keep webhook URLs (which embed the token) out of
  logs/screenshots, and can rotate the token in settings.
- The following must be confirmed against a live account and this ADR
  updated afterwards: exact event envelope key names; `connectTimeout`
  support on dialog `childCallRequest`; `customData` round-trip on
  events and in the WebRTC SDK (`callApplication` availability);
  recording entitlement, event shapes and file download path; the
  Numbers API SMS-forwarding and voice-action config schemas; the
  WhatsApp senders listing endpoint; the DLR `status.groupName`
  vocabulary; the Subscriptions API variant for auto-provisioning.
