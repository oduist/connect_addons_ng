# VoiceML integration

`connect_voiceml` is the provider module for **VoiceML** — VoiceTel's
Twilio-wire-compatible voice + SMS + AMD (answering-machine detection) service.

> **No account yet?** Sign up at <https://voicetel.com/signup/>, then sign in to
> the carrier portal at <https://www.voicetel.com/>. VoiceTel provisions a
> VoiceML account (`AccountSid` + API key); the API key is shown exactly once —
> save it immediately. See `installation.md` for the full flow.

Because VoiceML speaks the same REST surface and TwiML as Twilio, this module
is built in the image of `connect_twilio` (ADR-031 / ADR-032). It is fully
autonomous: it owns its PBX configuration models (`connect.voiceml.*`), extends
only the shared ledger models, and lives in its own **VoiceML** submenu of the
Connect app.

## How it differs from Twilio

| Aspect | `connect_twilio` | `connect_voiceml` |
|---|---|---|
| REST client | `twilio` package, host rewrite | `voiceml-python-sdk`, native `base_url` |
| Web phone | Twilio Voice JS SDK (`twilio.min.js` + JWT) | JsSIP (SIP-over-WebRTC) |
| Softphone registrar | Twilio cloud gateway | self-hosted OpenSIPS WSS edge |
| Webhook auth | `X-Twilio-Signature` (auth token) | `X-Twilio-Signature` (API key) |

## What it covers

- Numbers, extensions, call flows and outgoing caller IDs (full routing).
- SIP domains + credential lists + per-user SIP credentials (the resources the
  softphone registers with).
- TwiML applications, click-to-call originate, and inbound number routing.
- SMS send/receive.
- Signature-verified webhooks (`/voiceml/webhook/*`).

## Current scope

See `installation.md` for setup and `live-test.md` for the acceptance pass.
OutgoingCallerIds / ValidationRequests ride raw HTTP until the SDK wraps them;
account balance and WhatsApp are out of scope for the first cut.
