# 027 — EL agent over Twilio: set a valid Dial callerId (error 13247)

## Status
Accepted — 2026-06-01. Tracking: ODU-26.

## Context

Calling an ElevenLabs agent from a Twilio Voice JS (WebRTC) client fails
immediately with `CallStatus=busy`. The Twilio call-status webhook carries:

```
ErrorCode    13247
ErrorMessage Dial->SIP: Invalid caller ID, invalid chars
From/Caller  client:admin@19-fs-compat.sip.twilio.com
```

Flow: WebRTC client → TwiML app *"SIP Domain Calls"* →
`connect.domain.route_call` → `connect.exten.render` →
`connect_elevenlabs_twilio` `connect.elevenlabs_agent.render()`, which
emitted:

```xml
<Response>
  <Dial>
    <Sip>sip:agent_…@sip.rtc.elevenlabs.io:5061;transport=tls?X-Call-Sid=…</Sip>
  </Dial>
</Response>
```

The `<Dial>` had **no `callerId`**. When `callerId` is omitted, Twilio
uses the parent leg's `From` as the SIP caller ID — here the WebRTC client
identity `client:admin@…`. Those characters (`client:`, `@`, `.`) are not
valid for a `<Dial><Sip>` caller ID, so Twilio rejects the child leg with
error 13247 and the call ends as `busy`.

The sibling Twilio paths already guard against this:
`connect_twilio` `domain.originate_external_call` and `callflow.render`
both replace a `client:`/`sip:` caller with a real number. The EL render
was the only `<Dial><Sip>` path that skipped the guard.

The same bug was already fixed in the legacy `connect_addons` repo
(`connect_elevenlabs/models/agent.py::_resolve_caller_id`), whose
docstring names error 13247 explicitly. That implementation is the proven
reference for this decision.

## Decision

Set an explicit, Twilio-acceptable `callerId` on the EL `<Dial>`, ported
verbatim (logic-wise) from the working `connect_addons` implementation:

- Keep the caller **only** when it is a clean E.164 number
  (`startswith('+')` and the rest is digits) — a positive whitelist, so
  any non-E.164 caller (WebRTC `client:`, `sip:` URI, blank) is replaced.
- Otherwise fall back to the default DID
  (`connect.outgoing_callerid` with `is_default=True`).
- If no default is configured, fall back to the literal `"anonymous"`,
  which Twilio accepts — never emit an empty/invalid caller ID.

A real inbound PSTN caller (E.164) is preserved, so EL still sees the
genuine caller number when one exists.

### Deliberately NOT changed

- **SIP target stays `:5061;transport=tls`.** The legacy repo dials
  `:5060;transport=tcp`; ng intentionally moved to TLS:5061 (ADR-025
  follow-up, commit `a9cc39d`). Only the caller-ID handling is ported.
- **`_el_sip_identifier` routing is untouched.** The legacy repo routes
  by Called DID first then `agent_uid`; ng always uses `agent_uid`
  (per-agent SIP user-part). Unrelated to 13247.

## Implementation

`connect_elevenlabs_twilio/models/agent.py`:

- `render()`: `dial = Dial(callerId=self._resolve_caller_id(request))`.
- add `_resolve_caller_id(self, request)` implementing whitelist → default
  DID → `"anonymous"`.

Manifest bump `connect_elevenlabs_twilio` `1.1.4 → 1.1.5`.

## Consequences

- EL-over-Twilio calls from WebRTC/SIP clients connect instead of failing
  with 13247.
- Requires a default `connect.outgoing_callerid` for a meaningful caller
  number; without one the leg still connects but presents `anonymous`.
