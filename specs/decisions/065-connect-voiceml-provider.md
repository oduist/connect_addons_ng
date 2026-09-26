# 065: connect_voiceml — VoiceML provider module

## Problem

Add VoiceTel's **VoiceML** (the Twilio-wire-compatible voice + SMS + AMD
service) as another telephony provider. Per
ADR-031 the module must be fully autonomous: it owns its PBX configuration
models (`connect.voiceml.*`), extends only the shared ledger models
(`connect.call`, `connect.channel`, `connect.message`, `connect.recording`,
`connect.user`, `connect.settings`) and lives in its own **VoiceML** submenu
of the Connect app.

VoiceML is Twilio-compatible at the wire level, but it is not Twilio. The
load-bearing differences that had to be decided up front:

- **REST client.** The official `voiceml-python-sdk` (MIT) targets
  `2010-04-01` paths with the same HTTP Basic auth (`AccountSid` + `api_key`)
  and error envelope as Twilio, but exposes a **`base_url`** constructor
  argument, so the customer points it at their VoiceML host directly — no
  SDK host-rewrite is required.
- **SDK surface is a subset.** `voiceml-python-sdk` covers calls,
  conferences, queues, applications, recordings, incoming phone numbers,
  messages, SIP domains/credential lists/IP-ACLs and routes v2, but **not**
  `OutgoingCallerIds`, `ValidationRequests` or account `Balance`.
- **Softphone.** VoiceML has **no** Twilio Voice JS SDK gateway. Its browser
  phone is standard **SIP-over-WebRTC** (JsSIP) registered against a
  self-hosted **OpenSIPS WSS edge** (`wss://<node>:8443`), using the same SIP
  credentials the SIP Domains/CredentialLists REST provisions.
- **Webhooks** are signed `X-Twilio-Signature` (HMAC-SHA1) with the tenant
  API key, exactly like Twilio.

## Decisions

1. **`connect_voiceml` is a new provider, not a `connect_twilio` patch.**
   The provider-separation model (ADR-031) is preserved: VoiceML gets its own
   models, webhooks and settings form. The Twilio module remains untouched.

2. **Use `voiceml-python-sdk` for REST.** The module's only python dependency
   is `voiceml`. `connect.settings.get_client()` constructs
   `Client(account_sid, api_key, base_url=voiceml_base_url)`.

3. **Own minimal TwiML builder, no `twilio` dependency.** VoiceML consumes the
   same TwiML verbs Twilio does, but there is no reason to pull the `twilio`
   package just to emit XML. `connect_voiceml` ships
   `models/twiml_builder.py` (ElementTree-based) covering `Say`, `Play`,
   `Pause`, `Reject`, `Hangup`, `Redirect`, `Gather` + `Dial`/`Number`/`Sip`/
   `Client` — the same decision connect_telnyx made for TeXML (ADR-032).

4. **Webhook signature in stdlib.** `models/webhook.py` reimplements Twilio's
   `X-Twilio-Signature` (HMAC-SHA1 over URL + sorted form concatenation) with
   `hmac`/`hashlib` and compares constant-time. The key is the tenant API key,
   read with `sudo()` in the controllers.

5. **SIP domain/credential model mirrors connect_twilio.** VoiceML's SIP
   Domains/CredentialLists REST is identical to Twilio's, so
   `connect.voiceml.domain` + `connect.voiceml.user` provision a domain, a
   credential list bound to the domain for registration and call auth, and one
   SIP credential per user — the exact resources a JsSIP phone registers with.

6. **Softphone = JsSIP, not the Twilio JS SDK.** `connect.user` exposes
   `get_phone_config()` (username/password/domain/`wss_url`) instead of a JWT
   `VoiceGrant`. The frontend will be an OWL component driving a vendored
   JsSIP `UA` against the OpenSIPS WSS edge. Click-to-call stays server-side
   (`connect.settings.originate_call`), dialling the user's SIP URI via
   `<Dial><Sip>`, so the softphone only owns registration + audio.

7. **OutgoingCallerIds via raw HTTP until the SDK catches up.** The module
   talks to `/OutgoingCallerIds` and `/OutgoingCallerIds.json`
   (CreateValidationRequest) directly with `httpx` + HTTP Basic. This is
   temporary: when `voiceml-python-sdk` wraps the resource, the `_raw_client`
   adapter is deleted in favour of the SDK.

## Consequences

- `connect_voiceml` is a drop-in provider alongside `connect_twilio` /
  `connect_telnyx` / `connect_freeswitch`; per ADR-031 the duplicated areas
  (exten `dst`-Reference plumbing, callflow language list, E.164 caller-ID
  logic) are copied on purpose, not shared.
- The softphone is the one place that differs materially from Twilio: it is a
  SIP/WebRTC client, so the browser phone does not work against a Twilio
  account and vice-versa — by design.
- WhatsApp and account Balance are out of scope for the first cut (VoiceML
  messaging is SMS/MMS; Balance has no SDK wrapper).
