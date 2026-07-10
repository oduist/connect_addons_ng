# ADR-030: Pipecat AI voice agent over mod_audio_fork

## Status

Accepted.

## Context

Connect needs a low-latency inbound voice agent that answers a FreeSWITCH call,
runs STT → LLM → TTS, supports caller barge-in and can transfer the caller to a
human. Conversation results must be attached to the existing `connect.call`.
Pipecat 1.5.0 is an asyncio service and cannot run safely inside an Odoo worker.

The June 2026 FreeSWITCH integration report at phonesstillexist.com found the
return-audio path in `mod_audio_stream` unreliable and fell back to temporary
WAV files plus `uuid_broadcast`. That fallback had about 1.4 seconds median
latency and no effective barge-in.

## Options considered

- `mod_audio_stream`: a small WebSocket module, but its return-audio path has
  unresolved interoperability failures and cannot meet the barge-in goal.
- `mod_audio_fork`: bidirectional raw L16 WebSocket audio, server-to-module
  `killAudio`, markers, TLS and Basic authentication.
- LiveKit SIP: mature media infrastructure, but adds another SIP edge and a
  larger operational surface than this first FreeSWITCH-native version needs.
- WAV playback through ESL: operationally simple, but too slow and cannot stop
  buffered speech promptly when the caller interrupts.

## Decision

Run Pipecat in a dedicated FastAPI sidecar. FreeSWITCH attaches
`mod_audio_fork` to the answered channel at 16 kHz mono and parks the call.
The sidecar converts binary L16 frames to Pipecat frames and sends generated
L16 audio back as binary WebSocket frames. Pipecat interruption frames produce
`{"type":"killAudio"}` immediately.

The exact module source is vendored in `connect_freeswitch/deploy` because the
original upstream repositories are no longer stable build dependencies. Its
provenance and original dual-license notice are preserved alongside the code.

Call identity (`call_uuid`, `agent_id`) travels only in the WebSocket query
string. JSON metadata is deliberately empty because whitespace in the module's
command parser can split the FreeSWITCH application arguments.

FreeSWITCH authenticates to the sidecar with HTTP Basic auth: username
`pipecat`, password `PIPECAT_SERVICE_TOKEN`. The sidecar uses the same secret as
a Bearer token when requesting agent configuration or posting results to Odoo.
Odoo never accepts provider keys from the sidecar and only returns keys for the
configured provider to an authenticated request.

Transfer is an Odoo-mediated control operation: stop the media bug, then issue
`uuid_transfer` to the agent's configured extension. Hangup uses `uuid_kill`.

## Consequences

- FreeSWITCH images now build libwebsockets/Boost and load a vendored module.
- Sidecars are stateless per call and can scale horizontally behind WSS.
- The implementation target is first bot audio in under 1.4 seconds and prompt
  barge-in via `killAudio`; these remain deployment-level acceptance metrics.
- DTMF, outbound campaigns, Twilio transport and FlowManager IVR are deferred.
- The vendored code has an original dual-license notice, not an MIT license;
  redistribution must be reviewed against those terms.
