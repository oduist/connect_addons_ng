# 036 - Softphone Recording Controls

## Context

Twilio and FreeSWITCH softphones need in-call recording controls so a user can
start or stop recording without leaving the phone widget. The shared call and
recording ledgers live in `connect`, but provider APIs and live call identifiers
are provider-specific.

FreeSWITCH adds one extra constraint: Verto calls are live before Odoo receives
the CDR, so there is no reliable `connect.channel` row for access or state while
the call is active. Runtime state must be stored on FreeSWITCH channel variables.

## Decision

Core `connect.channel` owns the provider-neutral RPC surface:

- `get_softphone_recording_state(payload)`
- `start_softphone_recording(payload)`
- `stop_softphone_recording(payload)`

Core validates provider dispatch and, for providers with database channel rows,
checks that the requesting user is a call participant or a Connect admin.

Provider modules implement their own handlers:

- Twilio resolves the live `connect.channel` by `CallSid`, starts/stops Twilio
  Recordings through the REST API, and stores the control state on the channel
  row.
- FreeSWITCH resolves the live Verto UUID, checks caller ownership through
  FreeSWITCH channel variables, and starts/stops `uuid_record`. Runtime state,
  path, recording reference and errors are stored on the live UUID variables.

FreeSWITCH only infers an automatic recording when the live UUID carries the
`execute_on_answer=record_session ...` dialplan variable. User-level
`record_calls=True` alone is not enough, because Odoo-originated click-to-call
legs do not start `record_session` and must remain manually startable.

## Consequences

- Co-installed providers keep independent implementation details while sharing
  one RPC contract.
- FreeSWITCH start/stop failures reset the live UUID out of transitional states
  so the softphone can retry.
- Completed recording artifacts still enter the normal `connect.recording`
  ledger through provider webhooks.
