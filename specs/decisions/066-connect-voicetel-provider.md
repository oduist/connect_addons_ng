# 066: connect_voicetel — VoiceTel VoiceML provider module (Twilio-compatible)

## Problem

VoiceTel sells **VoiceML**, a self-hosted Twilio-compatible voice and
messaging platform (the `callBroadcast` Go service on FreeSWITCH, with an
OpenSIPS registrar in front of it). The product owner wants it available in
Connect as a provider in its own right, under the VoiceTel/VoiceML names.

VoiceML was evaluated from its own repository (`docs/api.md`, `docs/twiml.md`,
`docs/parity.md`, `docs/sdk-clients.md`, `docs/outgoing-caller-ids.md`,
`docs/accounts.md`, the served OpenAPI spec and the VoiceML Phone clients).
What matters for Connect:

- **REST**: `/2010-04-01/Accounts/{AC…}/…` with HTTP Basic `AccountSid:api_key`.
  Calls (create/update/fetch/list, `Twiml=`/`Url=` hot swap), Recordings
  (`/Calls/{Sid}/Recordings` incl. mid-call start/stop), IncomingPhoneNumbers
  (per-number `voice_url`/`sms_url`/`status_callback`), OutgoingCallerIds
  with the **real** verification call (`ValidationRequest` with
  `validation_code`, `StatusCallback` carrying `VerificationStatus` and
  `OutgoingCallerIdSid`), Applications, **SIP Domains + Credential Lists +
  Credentials + the five domain mappings**, Messages (SMS/MMS, status
  callbacks, inbound webhook with Twilio parameter names), Balance.
  Twilio helper libraries are the documented client: VoiceML tests all seven
  against its API, the only change being the host.
- **Webhooks**: `application/x-www-form-urlencoded`, `X-Twilio-Signature`
  (HMAC-SHA1 keyed with the account `api_key`, signed over the URL as
  transmitted — fragments dropped), standard Voice parameters plus `CallToken`
  on inbound calls, exactly-once delivery.
- **TwiML**: every Twilio voice verb except `<Pay>`; `<Dial>` with
  `<Number>`/`<Sip>`/`<Client>`/`<Conference>`; `<Gather>` DTMF and speech;
  `<Record>` with `recordingStatusCallback`. VoiceML calls the dialect
  **VoiceML** in customer-facing copy.
- **Browser calling**: there is **no** Twilio Voice JS SDK analog and no
  AccessToken/VoiceGrant. Devices register with SIP over WSS to the tenant's
  SIP domain `<label>.vml.voice.tel` (`wss://<label>.vml.voice.tel:8443`,
  OpenSIPS registrar, digest auth against the domain's credential list). The
  VoiceML Phone desktop app does exactly that with SIP.js. `<Dial><Sip>` to a
  `*.vml.voice.tel` address is routed by VoiceML through the registrar to
  the registered contacts. `<Dial><Client>` resolves to an internal
  `callbroadcast.local` profile and does **not** reach registered devices.
- **Recordings**: `RecordingUrl` is extension-less; the API serves the WAV
  with Basic auth, `302`s to a presigned S3 URL once the tenant's own bucket
  took it, and answers `410 Gone` once the local copy is cleaned up with no
  bucket configured. Recording storage is bring-your-own per tenant.
- **No** WhatsApp, no Twilio regions/edges, no Twilio API Key/Secret pairs
  (one `api_key` per account is both the Basic password and the signing key).

A previous attempt pointed `connect_twilio` at VoiceML through the host
override. It worked far enough to surface real bugs on both sides (the
409/404 findings of 2026-07-17 and 2026-07-31 in the VoiceML project), but it
is not a product: per ADR-031 a provider owns its numbering plan and models,
the per-user `originate_provider`/`message_provider` keys would both read
`twilio`, and the Twilio Voice SDK web phone can never work against VoiceML.

## Decisions

1. **New standalone provider module `connect_voicetel`**, provider key
   `voicetel`, models `connect.voicetel.{exten,callflow,callflow_choice,
   number,outgoing_callerid,user_callflow,user_callflow_call,voiceml,
   domain,message_configuration}`, routes `/voicetel/webhook/*`, menu
   **VoiceTel** under the Connect app, standalone settings form opened via
   `open_settings_form`. Depends on `connect` only. ADR-031 rules apply: it
   `_inherit`s only the shared ledger models and every contributed
   `connect.user`/`connect.settings`/`connect.call` field carries the
   `voicetel_` prefix so it co-installs with `connect_twilio`.

2. **`connect_twilio` is the structural template, copied — not
   `connect_telnyx`.** ADR-032 ported Telnyx from Twilio because TeXML was a
   subset with different SIP and messaging primitives. VoiceML is the
   opposite case: it implements the very resources the Twilio module is built
   on (SIP Domains, Credential Lists, Applications, OutgoingCallerIds with
   verification, IncomingPhoneNumbers, Messages). The render pipeline,
   number/exten/callflow/user models, webhook controllers, sync logic,
   recording controls and blind transfer port with a rename.

3. **The `voiceml` Python SDK is the client, and markup is built by the
   module's own VoiceML builder.** *Amended after review (operator decision):
   VoiceTel ships its own SDKs and the module uses them.* The original draft
   reused `twilio-python` with a host-rewriting HTTP client; that read as a
   Twilio integration and its string-matched error handling was fragile.
   `connect.settings.get_voicetel_client()` now returns a `voiceml.Client`
   (`account_sid`/`api_key`/`base_url` native, typed `ApiError` subclasses
   with `code`/`status_code`), webhooks validate with
   `voiceml.webhooks.RequestValidator` (drop-in `validate()`/
   `compute_signature()`), and VoiceML markup is rendered by
   `models/voiceml_response.py` — a ~100-line ElementTree builder mirroring
   the TwiML helper's API (the connect_telnyx precedent). The `twilio`
   package is no longer a dependency. Two SDK request models lack fields the
   server accepts — `StatusCallback` on `IncomingPhoneNumbers.update` and on
   the ValidationRequest create — so those two calls go through
   `connect.settings.voicetel_api_form()`, which rides the SDK transport
   (same auth/host/retries/error mapping) with an explicit form. Tracked
   upstream as voiceml-sdk tasks; the seam is removed once the SDK models
   carry the fields.

4. **Web phone = SIP over WSS with JsSIP, registered to the tenant's
   `*.vml.voice.tel` domain.** The `connect_asterisk` JsSIP phone is the
   template (same component set; `connect_twilio`'s phone is bound to
   `Twilio.Device`). A `connect.user` with `voicetel_sip_enabled` gets one
   SIP credential in the domain's credential list; hardphones and the browser
   phone register with the **same** credential, so one `<Dial><Sip>
   sip:<username>@<label>.vml.voice.tel</Sip></Dial>` rings every registered
   device. The Twilio `client` callflow type disappears; user callflow types
   are `sip` and `voicemail`. The browser phone is a per-user switch
   (`voicetel_phone_enabled`) that only governs the browser.

5. **The SIP password is stored readable by its owner, not masked.** The
   Twilio module masks the credential password after creating it because the
   web phone used a JWT. Here the browser needs the digest password, so
   `voicetel_password` keeps its value (`groups` admin + user, the core
   record rules keep a `connect.user` private to its owner) and reaches the
   browser only through `res.users.get_voicetel_sip_user_config(uid)`, which
   answers for the calling user alone — the ADR-032 decision 4 pattern. A
   blank password on enable is generated server-side.

6. **Click-to-call has two paths, chosen in the browser.** When the JsSIP
   phone is registered, the `phone` field widget places the call from the
   browser; the INVITE reaches VoiceML through the registrar, VoiceML fetches
   the SIP domain's `voice_url` and `connect.voicetel.domain.route_call()`
   routes it (extension → user/callflow/VoiceML app, `+E164` → `<Dial
   callerId=…><Number>`), exactly as the Twilio domain application does.
   Without a registered browser phone, `connect.settings.originate_call()`
   (key `voicetel`) creates the call with `To=sip:<username>@<domain>` and the
   inline `Twiml=` destination — the Twilio module's SIP-phone branch.
   VoiceML vets `sip:` destinations and dials `*.vml.voice.tel` names through
   the registrar.

7. **Recordings are pulled into Odoo on the status callback.** VoiceML keeps
   the WAV locally only until it is uploaded to the tenant's own bucket or
   cleaned up, and Connect holds no bucket credentials. So
   `connect.recording.on_voicetel_recording_status()` creates the ledger
   record and immediately downloads `RecordingUrl` (Basic auth, bounded
   timeout) into `recording_attachment`, like `connect_infobip`. The
   `media_url` is kept and `get_media_auth()` answers the VoiceML host, so a
   recording that could not be fetched in time still plays through the
   proxy while VoiceML serves it (following the S3 `302` without forwarding
   the credentials, which `requests` drops on a cross-host redirect).

8. **Webhook authentication: `X-Twilio-Signature` keyed with the account
   `api_key`.** All `/voicetel/webhook/*` routes validate with
   `RequestValidator(api_key)` over the https URL as transmitted plus the POST
   form (same query-string rule as the Twilio controller), toggled by
   `voicetel_verify_requests` (default on). No `#e=<edge>` fragments are put
   on callback URLs: VoiceML signs the URL without a fragment and the edge
   concept does not exist.

9. **SIP domain = Twilio-shaped SIP Domain + credential list + both
   `Auth/Registrations` and `Auth/Calls` mappings, under the
   `vml.voice.tel` suffix.** `connect.voicetel.domain.subdomain` is the
   tenant label; `domain_name = <label>.<voicetel_sip_suffix>`. The
   registrar only authenticates `*.vml.voice.tel` names, so the suffix is a
   setting (default `vml.voice.tel`) rather than free text. The routes
   `voice_region` calls and Twilio edge hostnames are dropped. The domain
   sync keeps its Odoo-wins rules; a `409`/`21631` "domain taken" answer is
   handled like Twilio's "already exists" (import by name, never a duplicate
   create) — the orphan-on-sync behaviour of the earlier attempt came from
   re-creating applications and domains on every failure.

10. **Messaging: SMS/MMS only**, through the core `connect.message.send()`
    dispatcher (key `voicetel`). Inbound messages arrive on
    `/voicetel/webhook/message` (`SmsStatus=received`), status callbacks on
    the same route with `MessageStatus`/`SmsStatus`. Every number gets its
    `sms_url` set (no US-region condition). WhatsApp senders, content
    templates and the WhatsApp composer are not ported.

11. **Outgoing caller IDs port in full**, including `validate()`: VoiceML
    places the verification call and reports on the status callback with the
    Twilio field names; owned numbers sync as `callerid_type='number'`.

12. **Call prices are kept** (VoiceML returns a `price` computed from the
    tenant's own rates once a call finalizes); the Twilio price cron ports
    under `voicetel_` field names. Twilio S3 external storage, regions/edges,
    WhatsApp calling and the Twilio API Key/Secret settings are **not**
    ported.

13. **Access rights mirror the Twilio matrix**, which the owner approved in
    ADR-031/ADR-032 for these same model shapes: Connect User read on the
    PBX-configuration models, Connect Admin full CRUD, webhook group read
    (plus write on `connect.voicetel.outgoing_callerid` for the verification
    callback), `connect.voicetel.message_configuration` admin-only.

14. **Duplicated-code rule now covers a fifth copy.** The exten dst-Reference
    mechanics, the caller-ID E.164/is_default logic and the BCP-47 language
    list exist in connect_twilio, connect_freeswitch, connect_telnyx,
    connect_infobip (no IVR) **and connect_voicetel**. A fix in one is
    applied to all in the same commit.

## Consequences

- New module `connect_voicetel` (version 19.0.1.0.0), depends `connect`,
  python dependency `twilio` (shared with `connect_twilio`).
- Frontend: JsSIP phone ported from `connect_asterisk` (`static/src/lib/
  jssip.min.js`), configured from `connect.settings.voicetel_get_phone_settings()`
  and `res.users.get_voicetel_sip_user_config()`; WSS URL is
  `wss://<domain_name>:8443`, tied to the SIP domain (constant
  `VOICETEL_WSS_PORT`, not a setting). If the VoiceML fleet ever moves the
  listener, the platform tells its tenants; the same constant lives in the
  VoiceML Phone clients and is changed there at the same time.
- Live verification against a VoiceML account is required before release:
  REST host rewrite through the helper library, SIP domain creation under
  the suffix, credential provisioning and WSS registration, inbound DID
  routing, `POST /Calls` with a `sip:` destination and inline `Twiml`,
  signature validation, recording download timing, SMS send/receive and the
  caller-ID verification call. These are listed in `specs/connect_voicetel.md`.
- No migrations — the module is new on 19.0; no 18.0 backport for now.
- A `connect_crm_voicetel` bridge (message routing to CRM leads, the
  `connect_crm_twilio` counterpart) is a follow-up, not part of this ADR.
