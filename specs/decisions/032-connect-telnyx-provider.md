# 032: connect_telnyx — Telnyx provider module (TeXML-first)

## Problem

Add Telnyx as the fourth telephony provider. Per ADR-031 the module must be
fully autonomous: it owns its PBX configuration models
(`connect.telnyx.*`), extends only the shared ledger models
(`connect.call`, `connect.channel`, `connect.message`, `connect.recording`,
`connect.user`, `connect.settings`) and lives in its own **Telnyx** submenu
of the Connect app. The product owner asked for a module "in the image of
connect_twilio", so the Twilio module is the structural template.

Telnyx differs from Twilio in several load-bearing ways that had to be
decided up front:

- Telnyx's native voice API is **Call Control** (JSON commands driven by
  webhooks), not XML instructions. Telnyx also offers **TeXML**, a
  Twilio-compatible XML translator with Twilio-shaped webhook parameters
  (`CallSid`, `From`, `To`, `CallStatus`, `Digits`, `RecordingUrl`, …).
- Webhooks are signed with **Ed25519** (`telnyx-signature-ed25519` +
  `telnyx-timestamp` headers over `{timestamp}|{payload}`), not
  HMAC-SHA1 `X-Twilio-Signature`.
- There is no "SIP domain + credential list" resource. SIP/WebRTC
  endpoints are **credential connections** carrying **telephony
  credentials** (per-user, auto-generated `sip_username`/`sip_password`,
  JWT via `POST /telephony_credentials/{id}/token`).
- There is no outgoing caller-ID validation API.

## Decisions

1. **TeXML over native Call Control.** The whole Twilio module is built
   around "webhook in → XML instructions out" (number/exten/callflow/user
   `render()` chains). TeXML keeps that architecture intact — controllers,
   render pipeline, gather/dial/record verbs and webhook parameter names
   port almost 1:1. Native Call Control would require a stateful
   command/event engine — a redesign, not a port. Call Control can be
   added later as an optional layer without breaking TeXML.

2. **Own minimal TeXML builder, no `twilio` python dependency.**
   `connect_telnyx` ships `models/texml_response.py` — a small
   ElementTree-based builder covering the verbs the module renders
   (`Say`, `Gather`, `Dial` + `Sip`/`Number` nouns, `Record`, `Pause`,
   `Hangup`, `Reject`, `Redirect`) with a `VoiceResponse`-like API. The
   module's python dependencies are `telnyx` and `pynacl` only.

3. **SIP domain analog = credential connection + PBX TeXML app with
   `sip_subdomain`.** `connect.telnyx.domain` manages two Telnyx
   resources:
   - a **credential connection** (`sid`) that hosts per-user telephony
     credentials (SIP registration for hardphones + WebRTC clients);
   - the **routing TeXML application** (`application` M2O) whose
     `inbound.sip_subdomain` is the domain's `subdomain`. Calls dialed to
     `sip:<dst>@<subdomain>.sip.telnyx.com` from the account's own
     connections hit the app's `voice_url`, so Odoo routes web-phone
     originated calls exactly like Twilio's domain app (`route_call`:
     exten → user/callflow/TeXML, `+E164` → external dial with the user's
     caller ID).

4. **Users = telephony credentials.** Telnyx generates
   `sip_username`/`sip_password`; they are stored readonly on
   `connect.user` (`telnyx_sip_username`, `telnyx_sip_password` — visible
   to the user for hardphone provisioning, unlike Twilio where the
   password is masked). The web phone logs in with a `login_token` JWT
   from `telephony_credentials.create_token()` — no account-level API
   keys reach the browser. Incoming legs to a user render as
   `<Dial><Sip>sip:<sip_username>@sip.telnyx.com</Sip></Dial>`.
   All `connect.user` fields/methods contributed by this module carry the
   `telnyx_` prefix (`telnyx_sip_enabled`, `telnyx_render_client`, …) so
   co-installation with connect_twilio (which owns the unprefixed names)
   keeps working.

5. **Webhook authentication: Ed25519.** All `/telnyx/webhook/*` routes
   (`readonly=False` — they write call history) validate
   `telnyx-signature-ed25519`/`telnyx-timestamp` over the raw request
   body with the account's public key (`telnyx_public_key` setting,
   PyNaCl), 5-minute timestamp tolerance, toggled by
   `telnyx_verify_requests` (default on). Must be confirmed against real
   TeXML traffic during live testing; the toggle is the escape hatch.

6. **Click-to-call originate via the TeXML REST API**
   (`POST /texml/Accounts/{account_sid}/Calls`, Twilio-compatible
   parameters). Requires the **`telnyx_account_sid`** setting (the
   account's TeXML Account SID / user ID from Mission Control) — Telnyx
   has no discovery endpoint for it.

7. **Outgoing caller IDs: owned numbers only.** Telnyx cannot validate
   external numbers, so `connect.telnyx.outgoing_callerid` keeps only
   `callerid_type = 'number'` records synced from the account's phone
   numbers. The `validate()` flow, `validation_code` and the webhook
   status callback are dropped.

8. **Numbers route through one shared voice webhook.** Telnyx numbers do
   not carry per-number voice URLs; they are attached to a TeXML app
   (`phone_numbers.update(connection_id=<app>)`). `connect.telnyx.number`
   assigns the number to the domain's routing app (voice) and to the
   module's messaging profile (SMS); inbound calls arrive on the shared
   `/telnyx/webhook/number` route and are dispatched by `To`.

9. **Messaging.** One messaging profile ("Odoo Connect") with
   `webhook_url` → `/telnyx/webhook/message`. Telnyx message webhooks are
   v2 JSON envelopes (`data.event_type` = `message.received` /
   `message.sent` / `message.finalized`), parsed natively (not
   Twilio-form-shaped). Sending uses `client.messages.send()`.
   **Known limitation:** like connect_twilio, the module implements the
   core abstract `connect.message.send()` and inherits `sms.composer`;
   co-installing connect_twilio and connect_telnyx leaves the last-loaded
   module owning SMS sending. Fixing this needs a core dispatcher hook
   (mirroring `originate_call`) — deferred, tracked for a core follow-up.

10. **v1 scope exclusions** (deliberate, to keep the port reviewable):
    WhatsApp (senders/templates/composer — Telnyx WhatsApp is a separate
    surface), RCS, attended transfer via conference
    (`connect.call.transfer()`), and Twilio-style regions/edges (Telnyx
    handles media anchoring via `anchorsite_override='Latency'`).

11. **Call prices: best-effort from detail records.** TeXML status
    callbacks do not carry cost. The Twilio price-fetch cron is kept but
    reads `client.detail_records.list(filter={'record_type': 'voice',
    …})`; failures are logged and retried, never blocking.

12. **Duplicated-code rule now covers three modules.** The exten
    dst-Reference mechanics, the callflow language list and the caller-ID
    E.164/is_default logic are full copies in connect_twilio,
    connect_freeswitch **and connect_telnyx** (ADR-031 "no mixins"
    stands). A fix in one must be applied to all three in the same
    commit.

13. **Access rights mirror the Twilio matrix** (owner-approved in
    ADR-031): user group read on PBX config models, admin full,
    webhook group read (no callerid write row — no validation callback);
    `connect.telnyx.message_configuration` admin-only.

## Consequences

- New module `connect_telnyx` (version 19.0.1.0.0), depends `connect`,
  python deps `telnyx`, `pynacl`.
- Frontend: the Twilio phone widget is ported to `@telnyx/webrtc`
  (TelnyxRTC client, `login_token` auth, `telnyx.notification` events);
  vendored as `static/src/lib/telnyx-webrtc.min.js`.
- No migrations — the module is new on 19.0; no 18.0 backport for now.
- Live verification against a real Telnyx account (TeXML signature
  format, subdomain routing, credential JWT) is required before release;
  install-level and UI-level checks run in the oduflow environment.
