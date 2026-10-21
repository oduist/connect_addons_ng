# Oduist Connect VoiceTel — Administrator Guide

`connect_voicetel` integrates **VoiceTel VoiceML** with the Oduist Connect
telephony platform for Odoo. VoiceML is VoiceTel's Twilio-compatible voice and
messaging platform: the REST API, the VoiceML call markup and the webhooks
follow the Twilio contract, so the module drives it with the Twilio helper
library pointed at the VoiceML host (ADR-066).

The module extends the shared Connect ledger (`connect.call`, `connect.channel`,
`connect.message`, `connect.recording`, `connect.user`, `connect.settings`) and
**owns its own PBX-configuration models** under the `connect.voicetel.*`
namespace (numbers, extensions, call flows, caller IDs, VoiceML apps, SIP
domains). It never imports code from other provider modules, so it can be
co-installed alongside Twilio, FreeSWITCH, Telnyx, Asterisk and the other
Connect providers.

## What this module provides

| Area | Capability |
|------|------------|
| **Voice** | Inbound routing (user / call flow / VoiceML app), click-to-call, blind transfer, call recording, voicemail |
| **Browser phone** | In-browser SIP phone (JsSIP over WSS) registered to the tenant's VoiceML SIP domain: incoming/outgoing calls, hold, mute, DTMF, transfer |
| **SIP** | SIP domains under `*.vml.voice.tel` and per-user SIP credentials, shared by desk phones, the VoiceML Phone apps and the browser phone |
| **IVR** | Call flows with `<Gather>` DTMF/speech menus and VoiceML applications (raw markup, Python, or model method) |
| **Messaging** | SMS/MMS send and receive, delivery status, routing of inbound messages to partners |
| **Caller IDs** | Owned numbers and verified external caller IDs (VoiceML places the verification call) |
| **Billing** | Optional per-call price fetching, account balance display |

## Prerequisites

- A running Odoo instance with the core `connect` module installed.
- The `voiceml` Python SDK available in the Odoo environment
  (`external_dependencies.python = ['voiceml']`). It is the documented client
  for VoiceML's API; no request ever leaves for Twilio.
- A VoiceML account: sign up at <https://voicetel.com/signup/>, complete
  KYC, then request the VoiceML account from
  [support@voicetel.com](mailto:support@voicetel.com) (see
  [Account Configuration](configuration.md#getting-a-voiceml-account)). You
  receive the **Account SID** (`AC…`) and the **API key**; the account needs
  at least one phone number, and the SIP domain suffix the registrar
  authenticates (`vml.voice.tel` by default).
- **A publicly reachable HTTPS URL for Odoo.** VoiceML delivers all events
  over webhooks and signs them against the URL it called.

## Guide contents

1. [Installation](installation.md) — installing the module and its dependency.
2. [Account Configuration](configuration.md) — credentials, API host, SIP
   suffix, sync, balance, options.
3. [Users, SIP & Browser Phone](users-and-sip.md) — SIP domains, per-user
   credentials and the browser phone.
4. [Numbers & Call Routing](numbers-and-routing.md) — inbound numbers,
   extensions, outgoing caller IDs.
5. [Call Flows & VoiceML Apps](call-flows-voiceml.md) — IVR menus and custom
   voice applications.
6. [Messaging (SMS)](messaging.md) — sending, receiving, routing.
7. [Webhooks & Security](webhooks-security.md) — routes, signature
   validation, access groups.
8. [Maintenance](maintenance.md) — scheduled jobs, licensing, troubleshooting.

## Menu location

Everything lives under the **Connect ▸ VoiceTel** submenu of the Connect app:
Numbers, Extensions, Call Flows, Outgoing Caller IDs, VoiceML Apps, SIP
Domains, Messages and Configuration.

!!! info "Administrator-only screens"
    Administrative screens (Configuration, message configuration) require
    the **Connect Administrator** group (`connect.group_admin`).
