# ADR-053: Preserve the raw Telnyx TeXML signature body

## Status

Accepted

## Context

Telnyx signs the timestamp and exact HTTP request body bytes. TeXML callbacks
use `application/x-www-form-urlencoded`, and Odoo parses that form before the
controller method runs. Reading the request body after parsing returns no
bytes, so the Telnyx controller reconstructed the form from parsed values and
tried common space encodings.

Form parsing is not reversible. For example, `+` and `%20` both decode to a
space, percent-escape casing is lost, and repeated fields may not retain a
byte-identical representation. A completed Dial action callback can therefore
have a valid Telnyx signature but fail verification after reconstruction. If
the external call leg remains active, returning a spoken security error also
plays that internal failure to the caller.

## Decision

1. The Telnyx module captures the original body bytes in
   `ir.http._pre_dispatch`, after Odoo has applied request size limits and
   immediately before the HTTP dispatcher parses form parameters. Capture is
   restricted to POST requests under `/telnyx/webhook/`.
2. Ed25519 verification uses only those original bytes. The controller does
   not accept reconstructed or canonicalized form bodies as fallbacks.
3. Missing raw bytes fail closed when request verification is enabled.
4. A rejected Dial action callback returns
   `<Response><Hangup/></Response>` so the remaining call leg ends silently.
   Other TeXML routes retain their existing invalid-request responses.
5. `telnyx_verify_requests` remains enabled and authoritative; this change
   does not weaken or bypass signature verification.

## Consequences

- Valid callbacks verify byte for byte even when they contain mixed `+` and
  `%20` spaces, signed URLs, repeated fields, or other non-canonical encoding.
- The request body is cached in memory for the lifetime of each Telnyx webhook
  request. Odoo's configured content-length limits are applied before capture.
- A third-party `ir.http._pre_dispatch` override that parses the form before
  delegating could still consume the stream prematurely; no such override is
  present in the supported stack.
- Invalid Dial action requests remain rejected but no longer expose a spoken
  implementation error to callers.

## Rejected alternatives

- Disable Telnyx request verification: this would accept forged callbacks.
- Try more reconstructed form encodings: no finite set can recover arbitrary
  original bytes from decoded form values.
- Keep the spoken invalid-request response for Dial actions: it leaks an
  internal verification failure into the live call and creates a poor caller
  experience.
