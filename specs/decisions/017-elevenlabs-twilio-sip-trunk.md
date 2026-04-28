# ADR-017: ElevenLabs ↔ Twilio SIP Trunk Transport

**Status:** Accepted
**Date:** 2026-04-29

## Context

`connect_elevenlabs_twilio` historically had one transport for connecting
a Twilio inbound call to an ElevenLabs Conversational AI agent: TwiML
`<Connect><Stream>` to the connect_elevenlabs relay
(`elevenlabs_agent_url`). The relay terminates the WebSocket and bridges
to ElevenLabs through the Conversational SDK (`TwilioAudioInterface`).
Structurally this is the analogue of `audio_fork` for FreeSWITCH
(ADR-016): full audio control, relay infrastructure required.

ElevenLabs now offers inbound **SIP trunking** as a first-class feature
(the same offering used by FS variant A in ADR-015). Twilio's TwiML
supports a direct SIP-bridge via `<Dial><Sip>sip:user@host</Sip></Dial>`,
which lets Twilio hand the call straight to the ElevenLabs SIP trunk —
no WebSocket, no relay.

## Decision

Mirror the FreeSWITCH bridge's two-transport pattern on the Twilio
bridge. Add a `twilio_transport` Selection on `connect.elevenlabs_agent`:

```python
twilio_transport = fields.Selection(
    [('media_stream', 'Twilio Media Streams (WSS to relay)'),
     ('sip_trunk',    'Twilio SIP-bridge to ElevenLabs trunk')],
    default='media_stream',
)
twilio_sip_host = fields.Char(default='sip.elevenlabs.io')
```

`render()` branches on `twilio_transport`:

- **`media_stream`** (default): unchanged — emits
  `<Connect><Stream url="wss://<relay>/twilio/stream/...">`.
- **`sip_trunk`**: emits
  `<Response><Dial><Sip>sip:<agent_uid>@<host>?X-Call-Sid=<CallSid></Sip></Dial></Response>`.
  Twilio appends the `X-Call-Sid` URI query param as a custom SIP header
  on the outbound INVITE so ElevenLabs can echo it back in tool webhooks.

`media_stream` stays the default to preserve current production behavior;
existing agents migrate seamlessly (the column defaults on upgrade).

### Why both

- **`media_stream` keeps the relay-side audio path** — recording,
  real-time analytics, prompt injection, and any custom audio mux that
  lives in `connect_elevenlabs/service`. Necessary for analytics-heavy
  deployments.
- **`sip_trunk` removes the relay from the call path** entirely — fewer
  moving parts, no WebSocket reachability concerns, no FastAPI deploy.
  Right when the agent is purely "answer DID, talk, hang up".
- They cohabit at the agent level: a different agent on the same Twilio
  number can use a different transport.

### Why ship `media_stream` as default

Existing agents must keep working after upgrade with no configuration
changes. `media_stream` is what production runs today.

## Transfer back to a human

The `transfer_to_agent` tool relies on Twilio REST
`client.calls(<sid>).update(twiml=<...>)`, which works on the parent leg
regardless of how it was originally directed (`<Connect><Stream>` or
`<Dial><Sip>`). Twilio terminates the current verb and runs the new
TwiML.

For `media_stream`, the parent SID is delivered to ElevenLabs through
the WebSocket metadata (relay forwards it). For `sip_trunk`, the parent
SID is passed as the `X-Call-Sid` SIP header on the outbound INVITE.
ElevenLabs must be configured to forward that header to the tool webhook
for transfer to function.

Agents deployed on `sip_trunk` without the `X-Call-Sid` plumbing on the
EL side will fail to transfer (the call sid won't match an active Twilio
call). This is a configuration prerequisite, not a new failure mode of
this ADR.

## Consequences

- `connect.elevenlabs_agent` gains two new columns
  (`twilio_transport`, `twilio_sip_host`).
- The Twilio bridge's `render()` now contains two TwiML shapes; tests
  exercise both.
- `docs/admin/elevenlabs-twilio.md` (follow-up) documents the SIP-trunk
  setup, ElevenLabs dashboard provisioning, and the X-Call-Sid header
  requirement for transfer.
- No relay-side changes for `sip_trunk`. The relay continues to serve
  `media_stream` agents — both can run side by side.

## Out of scope

- Outbound calls **originated by ElevenLabs** through Twilio (PSTN
  origination via Twilio SIP). Same plumbing in reverse but driven by
  EL's outbound API; tracked separately.
- Per-tenant SIP credentials (this ADR assumes one EL inbound trunk per
  Odoo database; agents differ only by the SIP user-part = `agent_uid`).
- Migrating existing agents from `media_stream` to `sip_trunk` in bulk —
  remains an admin choice per agent.
