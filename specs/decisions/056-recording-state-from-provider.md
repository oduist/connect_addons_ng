# ADR-056: Read live recording state from the provider, not from settings

**Status:** Accepted
**Date:** 2026-08-19

## Context

ADR-055 gave the Twilio softphone two explicit recording states: an idle
`REC` badge meaning *start*, and a purple `fa-stop-circle` meaning *stop*.
The state feeding those icons was inferred from configuration — when the
channel carried no control state of its own,
`_softphone_recording_state_twilio` reported `on` if
`connect.user.record_calls` was set on the call's PBX user.

That flag only governs recording for calls the user places or receives
directly (`connect.twilio.domain`). A call arriving through a callflow is
recorded by `connect.twilio.callflow.record_calls`, which puts
`record='record-from-answer-dual'` on the `<Dial>` and is an entirely
separate switch, defaulting off while the user flag defaults on.

Both mismatches were reachable with stock defaults:

- callflow not recording + user flag on — the phone offered **Stop
  Recording** for a call nobody was recording, and the click failed with
  `Could not stop recording` because Twilio has no such recording;
- callflow recording + user flag off — the phone offered **Start
  Recording** during a recorded call, and the click opened a *second*
  recording.

Recording can also be started outside Odoo entirely, which no
configuration flag can predict.

## Decision

Treat Twilio as the only authority on whether a recording is running.

- `_twilio_active_recording()` queries the Recording API for
  `status='in-progress'` and returns the `(call_sid, recording_sid)` pair
  that is live.
- It searches `_twilio_recording_call_sids()` — this leg first, then the
  parent chain — because a callflow records on the leg running `<Dial>`
  (the parent) while the softphone holds the client child leg.
- `_softphone_recording_state_twilio` uses that result instead of the
  `record_calls` heuristic, which is removed.
- `_softphone_recording_stop_twilio` resolves the same way, so stop acts on
  the leg that carries the recording; it falls back to `channel.sid` plus
  `Twilio.CURRENT` only when nothing live is found.
- Lookup failures are logged and degrade to `off`, leaving the manual start
  action available.

FreeSWITCH already reads `odoo_recording_state` from the live channel and
needs no equivalent change.

## Consequences

- The icon matches reality for callflow calls, direct calls, and recordings
  started outside Odoo.
- Stop acts on the recording the user can see, so the control no longer
  fails on calls it claimed to be recording.
- `connect.user.record_calls` returns to being purely an automatic-recording
  setting; it no longer drives any UI state.
- Each state sync costs one Twilio API call per leg examined, on call start
  rather than on a timer.
