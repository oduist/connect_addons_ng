# connect_voiceml — VoiceML module spec

Provider module for **VoiceML** — VoiceTel's Twilio-wire-compatible voice + SMS
+ AMD service. Built in the image of `connect_twilio`
(ADR-031 / ADR-032); design decisions live in
`specs/decisions/065-connect-voiceml-provider.md`.

## Models

Owned by the module (fully independent per ADR-031):

| Model | Purpose |
|---|---|
| `connect.voiceml.application` | TwiML application (`<Dial><Application>` + stored TwiML). The `connect_twilio.twiml` counterpart. |
| `connect.voiceml.domain` | SIP domain + credential list (bound for registration + call auth). |
| `connect.voiceml.number` | Inbound number → user / callflow / application routing. |
| `connect.voiceml.exten` | Extension (`dst` Reference to user / callflow / application). |
| `connect.voiceml.callflow` + `connect.voiceml.callflow_choice` | IVR call flow (gather + ring users + voicemail). |
| `connect.voiceml.outgoing_callerid` | Outgoing caller IDs (list + validation). |

`_inherit`-ed ledger models: `connect.settings`, `connect.user`, `connect.call`,
`connect.channel`, `connect.message`, `connect.recording`.

## Settings

`connect.settings` gains: `account_sid`, `api_key` (admin-only; both the SDK
auth token and the `X-Twilio-Signature` key), `voiceml_base_url`,
`voiceml_wss_url` (OpenSIPS registrar), `voiceml_auto_sync`,
`voiceml_verify_requests`. A standalone **VoiceML** settings form + sync button
mirrors the other providers.

## REST client

`get_client()` builds `voiceml.Client(account_sid, api_key,
base_url=voiceml_base_url)`. The module's only Python dependency is `voiceml`.
OutgoingCallerIds / ValidationRequests ride raw `httpx` against
`/2010-04-01/Accounts/{sid}/OutgoingCallerIds(.json)` until the SDK wraps them.

## TwiML

`models/twiml_builder.py` — a small ElementTree builder (`Say`, `Play`, `Pause`,
`Reject`, `Hangup`, `Redirect`, `Gather` + `Dial`/`Number`/`Sip`/`Client`), so
no `twilio` package is pulled in just to emit XML.

## Webhooks

`/voiceml/webhook/*` (12 routes) validated with `X-Twilio-Signature`
(HMAC-SHA1 over URL + sorted form, stdlib in `models/webhook.py`, byte-identical
to `twilio-python`'s `RequestValidator.compute_signature`, port-tolerant).

| Route | Handler |
|---|---|
| `/voiceml/webhook/domain` | `connect.voiceml.domain.route_call` |
| `/voiceml/webhook/number` | `connect.voiceml.number.route_call` |
| `/voiceml/webhook/callstatus` | `connect.call.on_call_status` |
| `/voiceml/webhook/callaction` | `connect.call.on_call_action` |
| `/voiceml/webhook/recordingstatus` | `connect.recording.on_recording_status` |
| `/voiceml/webhook/vm_recordingstatus` | `connect.call.on_vm_recording_status` |
| `/voiceml/webhook/outgoing_callerid` | `connect.voiceml.outgoing_callerid.update_status` |
| `/voiceml/webhook/callflow/<id>/gather` | `connect.voiceml.callflow.gather_action` |
| `/voiceml/webhook/<model>/call_action/<id>` | `on_call_action` |
| `/voiceml/webhook/application/<id>` | `connect.voiceml.application.render` |
| `/voiceml/webhook/message` | `connect.message.receive` |
| `/voiceml/webhook/message_status` | `connect.message.receive` |

## Softphone

JsSIP (SIP-over-WebRTC), **not** the Twilio Voice JS SDK. `connect.user`
exposes `get_phone_config()` (username/password/domain/`wss_url`) instead of a
JWT `VoiceGrant`. The frontend (`static/src/components/phone/`) registers a
JsSIP `UA` against the OpenSIPS WSS edge and answers incoming INVITEs;
click-to-call is server-driven via `connect.settings.originate_call`, which
dials `sip:username@domain`.

## Originate

`originate_call` dispatches on `_get_originate_provider(user) == 'voiceml'`,
creates the call with `client.calls.create(CreateCallRequest(...))` (TwiML that
dials the destination), and records the channel into the ledger.

## Scope and limitations

Out of scope for the first cut: account balance, WhatsApp (VoiceML is
SMS/MMS), softphone keypad/transfer UI. See `docs/installation.md` and
`docs/live-test.md`.
