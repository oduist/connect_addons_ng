# ADR-015: ElevenLabs ↔ FreeSWITCH Transport

**Status:** Superseded by ADR-020
**Date:** 2026-04-28

## Context

`connect_elevenlabs_freeswitch` is currently a stub: `agent.render()` and
`agent.transfer()` log a warning and return nothing. To deliver an ElevenLabs
conversational agent reachable from a FreeSWITCH-routed call we need a
provider bridge analogous to the Twilio one (`<Connect><Stream>` to
`elevenlabs_agent_url`).

ElevenLabs Conversational AI exposes two integration paths suitable for
FreeSWITCH:

1. **SIP Trunking** — admin provisions a SIP trunk in the ElevenLabs
   dashboard, ElevenLabs returns SIP credentials and a SIP URI. FS bridges the
   call leg to a `sofia/gateway/elevenlabs/...` dial-string, ElevenLabs
   terminates the audio and runs the agent. Transfer back is via SIP REFER
   (or ESL `uuid_transfer` triggered by an EL webhook).

2. **WebSocket via `mod_audio_fork`** — FS forks raw audio into a WebSocket
   handled by our relay (`elevenlabs_agent_url`). The relay is the same
   process that terminates Twilio Media Streams; we add an FS-aware endpoint
   that converts FS L16 frames to ElevenLabs WS frames and back. Transfer is
   ESL `uuid_transfer` initiated from a webhook EL fires when the agent
   invokes the `transfer_to_agent` tool.

3. **Custom ESL bridge with no relay** — Odoo opens an ESL connection and a
   WSS connection to EL and shuttles frames. Rejected: same audio-handling
   surface as option 2 but without reuse of the existing relay; pure cost.

## Decision

Implement both **(A) SIP Trunking** and **(B) `mod_audio_fork` WebSocket**,
selectable per agent via an `fs_transport` Selection field on
`connect.elevenlabs_agent`. Default = `sip_trunk`. Ship A first as MVP, B as
a second sprint.

```python
fs_transport = fields.Selection(
    [('sip_trunk', 'SIP Trunk to ElevenLabs'),
     ('audio_fork', 'WebSocket via mod_audio_fork')],
    default='sip_trunk',
    string='FreeSWITCH Transport',
)
```

`generate_dialplan(params, exten)` lives in
`connect_elevenlabs_freeswitch.models.agent` and branches on `fs_transport`.
`transfer(channel_sid, exten)` uses ESL `uuid_transfer` for both modes
(REFER flows are handled by mod_sofia transparently when EL initiates them).

### Why both

- **A is the default**: zero audio-handling code, zero changes to the FS
  Docker image, ships in days. Covers the standard "agent answers a DID"
  use case.
- **B is the escape hatch**: when an admin needs latency control, custom
  audio processing, or operates an EL plan without SIP trunking, they flip
  the agent to `audio_fork`.
- They cohabit with no coupling: a different agent can use a different
  transport, and the existing Twilio bridge keeps working independently.

## Consequences

- **Sprint 1 (this ADR delivers):** variant A. New gateway record, SIP-bridge
  dialplan generator, REFER-based transfer, agent UI tab.
- **Sprint 2 (separate ADR-016 when started):** variant B. Adds
  `mod_audio_fork` to the FS Docker image, a `/freeswitch/stream/...`
  endpoint to the relay, and an ESL transfer hook.
- `connect.elevenlabs_agent.render()` is **not used** in the FreeSWITCH path.
  FS routing goes through `connect.exten.generate_dialplan` →
  `dst.generate_dialplan` (where `dst` is the agent record). The Twilio
  `render()` overload is left untouched.
- The ElevenLabs side requires manual provisioning per environment: admin
  creates a SIP trunk in the EL dashboard, supplies the credentials when
  creating the `connect.freeswitch.gateway` record. Documented in
  `docs/admin/elevenlabs-freeswitch.md`.
- An agent's `fs_transport = 'audio_fork'` will be rejected with a UI-level
  validation message until Sprint 2 ships.

## Out of scope

- Outbound calls **originated by ElevenLabs** through our FS gateway
  (i.e. EL initiates calls to PSTN via our trunk). Same SIP plumbing in
  reverse but driven by EL's outbound-call API; tracked separately.
- Multi-tenant SIP credentials. The MVP assumes one EL SIP trunk per Odoo
  database (one `connect.freeswitch.gateway` named `elevenlabs`).
- Failover between A and B at call time. Switching transport is an admin
  action on the agent record, not runtime.

## Errata (post-implementation findings, 2026-04-29)

Two assumptions in the original draft turned out to be wrong once the
trunk was provisioned end-to-end against ElevenLabs. The template and
docs have been corrected; recording the correction here so the mental
model matches reality.

1. **Routing key is the EL trunk's `phone_number`, not `agent_uid`.**
   ElevenLabs binds an inbound trunk to a `phone_number` (an arbitrary
   string admin sets when provisioning, e.g. `1927`). Inbound INVITEs
   are dispatched by matching the SIP user-part against that
   `phone_number`, not against the agent_id. The dialplan template now
   uses `{{ extension_number }}` (= the dialed Odoo extension, which by
   convention equals the trunk's `phone_number`) as SIP user-part. The
   `agent_uid` is still passed as an `X-Agent-Id` SIP header for
   logging/visibility, but it is not load-bearing for routing.

2. **Codec must be forced to `PCMU`/`PCMA` on the dial-string.**
   When FS bridges from an inbound leg whose codec is `L16` (loopback,
   internal soft-bridges, etc.), `inherit_codec` defaults to true and
   sofia offers `L16/8000` to EL, which responds `500` after
   `180 Ringing`. The template now prefixes the bridge target with
   `{absolute_codec_string='PCMU,PCMA'}` so the outbound leg negotiates
   `PCMU/PCMA` regardless of the inbound codec.
