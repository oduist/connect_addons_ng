# ADR-058: Caller ID of a user without an extension

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

A second, related defect is visible even when the extension *is* set. Twilio
E.164-prefixes a bare extension used as caller ID, so the callee's web phone
was handed `From=+101` and displayed that. `connect.channel._strip_exten_plus()`
(ADR from the click-to-call fix) already repairs this for the ledger, but the
browser has no extension list to repair it with.

## Decision

**One caller ID for both paths.** Add `connect.user.twilio_caller_id()` and
use it in `_get_caller_id()` and `originate_call()`. It walks a ladder:

1. the user's extension — the identity a colleague should see;
2. the user's own `twilio_outgoing_callerid`;
3. the default outgoing caller ID (`is_default`);
4. the client identity `client:<username>@<domain>` — accepted by Twilio for
   both `<Dial callerId>` and the REST `From`, and resolved back to the
   calling user by `connect.channel._get_channel_numbers()`.

The warning is kept and now names the value used. Steps 2–4 exist so that no
call ever goes out with an empty caller ID; assigning the extension makes
step 1 answer and the rest never runs.

**The web phone is told the caller ID directly.** `render_client()` adds
`<Parameter name="From" value="<callerId>"/>` to the `<Client>` verb. The
widget already prefers `session.customParameters.get('From')` over
`session.parameters.From`, so it shows `101` instead of Twilio's `+101`
without any change to the JS. A SIP endpoint still sees the E.164 form in the
`From` header — SIP takes no custom parameters.

The parameter is sent **only for a bare extension** (digits, at most
`MAX_EXTEN_LEN`). That is the one caller ID Twilio rewrites; every other value
— E.164, `whatsapp:+…`, a client identity — already reaches the browser
intact as Twilio's own `From`, and overriding it would put the value through
Twilio's custom-parameter encoding for no gain.

Click-to-call builds the same parameter itself, in the `client:…?…&From=`
query of the leg it originates. There the number is sent without its `+`
(a plus decodes as a space in a query string) and, for a WhatsApp call, with
the `whatsapp:` prefix — the widget reads that prefix as "show the WhatsApp
badge", and without it an outgoing WhatsApp call looked like a plain call.

## Alternatives considered

**Raise a `ValidationError` in `originate_call()` when the caller has no
extension.** Loud and actionable, in line with the WhatsApp sender check, but
it blocks click-to-call entirely over what is a cosmetic defect on the
callee's screen, and it cannot be applied to the dialplan path: raising
inside webhook rendering drops a live call. Two different behaviours for one
missing setting is worse than one honest fallback.

**Strip the `+` in the web phone widget.** The browser would have to guess
which `+<digits>` values are extensions and which are real short numbers —
the same guess `_strip_exten_plus()` only makes safely because it can query
`connect.twilio.exten`. The server already knows the answer, so it says it.

## Notes

Extensions are assigned by hand (**Extension** button on the PBX User form,
`create_twilio_extension()`); nothing assigns one automatically on user
creation. A database can therefore always contain PBX users without an
extension, which is why the fallback has to be defined rather than left to
Twilio.
