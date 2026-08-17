# ADR-068: Guard the Telnyx AI assistant voice speed range

## Status

Accepted.

## Context

An assistant configured with `voice_speed = 2.0` on the
`Telnyx.Ultra.00a77add-48d5-4ef6-8157-71e5437b282d` voice answered every call
and hung up after one second. The call-progress webhook reported
`CallStatus=conversation_ended`, `Reason=greeting_error`, `DurationSec=1` and
an empty `Messages` list; `GET /ai/conversations/<id>` reported
`error: "The assistant could not generate the greeting audio."` with zero
messages. Comparing the assistant versions returned by
`GET /ai/assistants/<sid>/versions` isolated the change: only `voice_speed`
(1.0 to 2.0), the transcription language and a recreated tool id differed from
the previous, working version, and neither transcription nor tools take part
in greeting synthesis.

A direct probe of `POST /v2/text-to-speech/speech` with the same voice and an
explicit `voice_settings` object reproduced the failure without a call:

| voice_speed | result |
| --- | --- |
| 0.5 | `400` — code `90103` "Failed to produce text to speech" |
| 0.8, 1.0, 1.2, 1.3, 1.5 | `200` — audio returned |
| 1.8, 2.0 | `400` — code `90103` |

Telnyx documents the range `[0.25, 2.0]`, but that range covers Telnyx Natural
voices; other voices reject speeds they do not support. Odoo published any
float, so an out-of-range value produced a silently unusable assistant: the
Telnyx write succeeded, no error surfaced in Odoo, and the defect appeared only
as short calls in the call ledger.

Official references:

- https://developers.telnyx.com/api-reference/assistants/create-an-assistant
- https://developers.telnyx.com/docs/voice/tts/providers/telnyx/ultra

## Decision

Constrain `connect.telnyx.ai_assistant.voice_speed` to `[0.5, 1.5]` with a
Python constraint, so an unsupported speed is refused in the form instead of
reaching Telnyx. The field help states the range, warns that a rejected speed
ends the call without a greeting, and records that Telnyx Ultra needs at least
0.8.

The bounds are an administrative guard rather than a per-voice capability
table: Telnyx publishes no machine-readable speed range per voice, and a table
maintained in Odoo would drift. Administrators still verify their own voice,
and 1.0 remains the safe default.

`_remote_values` clamps a remote speed into the same range so one unusable
value read back from Telnyx cannot fail the local constraint and abort the
whole synchronization.

## Consequences

- A speed that breaks greeting synthesis on common voices is rejected at the
  point of entry, with an explanatory message.
- Speeds between 0.5 and 0.8 remain reachable for voices that support them,
  and are still capable of breaking Telnyx Ultra — the help text carries that
  warning instead of a narrower hard limit.
- Existing assistants stored above 1.5 must be lowered before their next
  write; a remote value above 1.5 is normalized to 1.5 on read.
- Telnyx-side greeting failures remain visible only in the conversation
  record; surfacing `greeting_error` in the Odoo ledger is a separate change.
