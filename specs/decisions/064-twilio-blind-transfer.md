# 064 — Blind transfer redirects the other leg through the routing app

## Problem

The softphone has always offered a **Forward** control and a picker to choose
who to forward to, and it has never worked. Three stubs, none of them wired to
anything:

- `phone.js::_busPhoneMakeForward` — the transfer line commented out behind a
  `// TODO: fix forward`, present since the initial commit (`31dc9e0`);
- `connect_twilio/models/call.py::transfer()` — a prototype that conferences
  both legs, with a hardcoded developer host `sip:user@devmax17.sip.twilio.com`;
- `connect_twilio/models/channel.py::transfer()` — a redirect to
  `<Response><Say>Ahoy there</Say></Response>`.

The commented-out line sent DTMF `*7<number>#`, a FreePBX/Asterisk feature
code. Twilio has no such concept and nothing in the TwiML app captures digits,
so it would not have worked uncommented either.

## Options considered

1. **Build TwiML for the destination in the forward handler.** Straightforward
   until you notice it means deciding, again, whether a destination is an
   extension or an external number, which client or SIP endpoint an extension
   resolves to, and which caller ID to present. All of that already exists in
   `connect.twilio.domain.route_call()`. A second copy would drift from the
   first the moment either changes.

2. **Conference both legs, then drop ours** (what the abandoned prototype
   started). Conferences are how *attended* transfer gets built, and they cost
   an extra leg and extra Twilio minutes. For a blind transfer nobody needs to
   be held anywhere.

3. **Redirect the other leg back through the routing application.**

## Decision

Option 3. `connect.channel.forward_softphone_call(payload)` in core dispatches
to `_softphone_forward_<provider>`, mirroring the recording controls; the
Twilio implementation redirects the **other party's leg** to the SIP domain's
TwiML application with the destination in a `forward_to` query parameter, and
`route_call()` prefers `forward_to` over `To`.

Consequences of that shape:

- **Routing is not reimplemented.** A forwarded call is routed by exactly the
  rules that route a dialled one. Verified in the tests: `forward_to=100`
  renders the same TwiML as dialling `100`.
- **It works in both directions.** On an inbound call the other leg is the
  customer; on an outbound one it is the person we called. Either way it is the
  party who should end up talking to the target, and our own leg drops when
  Twilio tears the bridge down. No direction-specific branch.
- **The ledger stays coherent.** The redirected leg keeps its `CallSid`, so
  `on_call_status()` updates the existing channel instead of opening a second
  call.

## Access

`forward_softphone_call` reuses `_softphone_recording_channel()` and
`_check_softphone_recording_access()`: resolving "which live leg is this
softphone on, and may this user touch it?" is not specific to recording. The
helpers keep their names — they are overridden per provider and renaming them
would ripple — but the `AccessError` message lost the word "recording", since
it now guards two features.

## Note

The `+` was being stripped from the destination on the way out
(`_onClickMakeForward`), left over from the DTMF idea, where a sequence could
not carry one. It is sent whole now: an external destination has to stay in
E.164 or `route_call()` stops recognising it as external.

## Checked against the shipping implementation

`oduist/connect_addons` (the pre-ADR-031 generation) has a working transfer in
`connect/wizard/transfer.py`. Two things it does that were adopted here:

- **It announces before moving the caller** — `<Say>Transferring your call
  now.</Say>` then a one-second pause, then the redirect. Being redirected
  mid-sentence with no warning reads as a dropped call.
- **It ends the agent's own leg.** Its `_busPhoneMakeForward` calls
  `endCall()` afterwards, and for outgoing calls it explicitly hangs up the
  original leg. This matters: on an inbound call Twilio kills our leg as soon
  as the customer is redirected away, but on an outbound one our leg is the
  one running the `<Dial>` — that Dial merely completes and the leg lives on,
  stranding the agent on a call with nobody.

Two differences kept deliberately:

- It redirects to a per-extension URL (`connect/<exten>`) and handles external
  numbers through a separate `<Dial><Number>` branch. Redirecting through
  `route_call` with `forward_to` covers both with one path, so extensions and
  external numbers cannot drift apart.
- It resolves which leg to move by asking Twilio for the call's parent, then
  branches on `direction` for outgoing calls — where it has to refuse when the
  external leg is untracked, because redirecting the agent leg would tear down
  its `<Dial>` and drop the external party.

  Picking the *sibling leg from the ledger* reaches the same answer in both
  directions without the branch: the sibling of the agent's leg is the customer
  inbound and the callee outbound, and it is never the agent's own leg, so the
  trap cannot be stepped in. It also costs no round-trip in the middle of a
  live call.

  But the ledger only answers when it is complete. A channel row still in
  flight, or a third leg left up by a ring group, and there is no single
  sibling to name — and refusing there blocks a transfer the user can plainly
  see is possible, which is exactly the case the reference handles and this
  did not. So the two are combined: **ledger first, Twilio as the fallback.**
  `_forward_target_sid()` takes the sibling when there is exactly one, and
  otherwise asks Twilio for our parent (inbound: we are the child) or our live
  child (outbound: we are the parent). The fast path stays free, and the
  robustness of the reference is there when the ledger cannot answer.

It also confirms this ADR's scope decision: in that product `_busPhoneMakeForward`
and `_busPhoneMakeTransfer` are byte-identical, both calling
`execute_transfer(..., 'blind', ...)`. The wizard has an `'attended'` branch
that the UI never reaches. Transfer and forward are one operation there too.

## The dead transfer path

The softphone also carried a second, separate transfer path: `_onClickTransfer`,
`state.isTransfer`, a `busPhoneMakeTransfer` trigger in `connect_twilio`'s
contacts list, an `attended_transfer_sequence = '*7'`, and a transfer mode in
the search results. None of it was reachable — the Transfer button had been
commented out of the template since the initial commit, and `phone.js` never
listened for `busPhoneMakeTransfer`. It was removed rather than wired: blind
transfer is what the picker offers and `forward_softphone_call` now provides
it, so a second half-built path alongside it was only ever going to mislead.

Attended transfer is deliberately out of scope. It needs conference-based leg
handling and panel states for "calling target / complete / cancel"; this ADR
covers the blind transfer the existing picker already promises.
