# ADR-058: A caller without an extension calls as its client identity

**Status:** Accepted
**Date:** 2026-08-21

## Context

Both Twilio call paths derived the caller ID of an outgoing call from the
caller's own extension, and both accepted an empty string when the PBX user
had none:

- `connect.user._get_caller_id()` — used by `render_client()` / `render_sip()`
  for the `<Dial callerId="...">` of a call routed through a dialplan;
- `connect.settings.originate_call()` — `callerId = user.connect_user.
  twilio_exten.number` for the `From` of the click-to-call REST originate.

An empty caller ID is not neutral. Twilio replaces it with an arbitrary
number of its own, and that number is what the callee's phone rings with and
what the status webhook reports back as `Caller`. In a database where a PBX
user had no extension, an internal call showed:

| Path | Ledger caller |
|------|---------------|
| Web phone → extension | `demo` — the login, via `client:demo@…` |
| Click-to-call → extension | `+32573` — invented by Twilio |

Neither is the caller. The only signal was a `logger.warning('Exten not set
for user %s')` that nobody reads, so a missing extension looked like a
ledger bug rather than a configuration gap.

## Decision

Add `connect.user.twilio_caller_id()` and use it on both paths. It returns
the extension when one is assigned, and otherwise the caller's client
identity — `client:<username>@<domain>` — which Twilio accepts as a caller ID
for both `<Dial>` and the REST `From`, and which the ledger already resolves
back to the calling user (`connect.channel._get_channel_numbers()` maps
`client:x@y` through `get_user_by_uri()`). The warning is kept and now names
the identity used instead.

Consequences:

- No call ever goes out with an empty caller ID, so Twilio never substitutes
  a number of its own.
- The ledger attributes such a call to the real caller: it reads `demo`, the
  same value the inbound leg already carried, instead of a bogus `+32573`.
- Assigning the extension remains the fix — `twilio_caller_id()` then returns
  `101` on both paths without any further change.

## Alternatives considered

**Raise a `ValidationError` in `originate_call()` when the caller has no
extension.** Loud and actionable, in line with the WhatsApp sender check, but
it blocks click-to-call entirely over what is a cosmetic defect on the
callee's screen, and it cannot be applied to the dialplan path: raising
inside webhook rendering drops a live call. Two different behaviours for one
missing setting is worse than one honest fallback.

**Fall back to the default outgoing caller ID.** It presents an external
PSTN number to a colleague on an internal call, and the ledger then reads
that number as an outside caller — the same class of wrong answer as the
number Twilio invents.

## Notes

Extensions are assigned by hand (**Extension** button on the PBX User form,
`create_twilio_extension()`); nothing assigns one automatically on user
creation. A database can therefore always contain PBX users without an
extension, which is why the fallback has to be defined rather than left to
Twilio.
