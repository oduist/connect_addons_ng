# 057 - Use the child Dial status for Telnyx fallback routing

## Status

Accepted

## Context

Telnyx TeXML sends both `CallStatus` and `DialCallStatus` to a Dial action
callback. They describe different call legs: `CallStatus` is the parent PSTN
leg, while `DialCallStatus` is the child destination leg created by `<Dial>`.

After an answered SIP destination hangs up normally, the callback can contain
`CallStatus=in-progress` together with `DialCallStatus=completed`. The user
action handler previously preferred `CallStatus`, treated the successful child
leg as unfinished, and advanced the user's fallback chain to voicemail. The
external caller then heard the voicemail greeting after an answered call.

## Decision

1. The Telnyx user Dial action handler uses `DialCallStatus` as the
   authoritative result of the attempted destination leg.
2. `CallStatus` is used only as a compatibility fallback when
   `DialCallStatus` is absent.
3. A `completed` destination leg terminates the parent leg with `<Hangup/>` and
   never advances to another user callflow step.
4. Only explicit unsuccessful results (`busy`, `no-answer`, `failed`, and
   `canceled`) advance the user fallback chain.
5. Missing or unknown results fail closed with `<Hangup/>` instead of starting
   another destination or voicemail.

## Consequences

- Voicemail remains available for calls that were not connected, but it cannot
  start after a caller has already spoken to a SIP or web-phone destination.
- Parent and child statuses may conflict without making routing ambiguous.
- Legacy callbacks that provide only `CallStatus` retain their previous
  completed/failure behavior for recognized values.
- Unexpected provider statuses end the call safely and are logged for
  diagnosis rather than triggering an unintended fallback.

## Rejected alternatives

- Prefer `CallStatus`: it describes the still-active parent leg, not the result
  needed to decide whether fallback routing is appropriate.
- Advance on every result except `completed`: an unknown or incomplete status
  could incorrectly ring another endpoint or start voicemail after a connected
  call.
- Remove fallback routing entirely: explicit missed-call outcomes still need to
  continue through the configured user callflow.
