# 054 - Telnyx bare SIP URI routing

## Status

Accepted

## Context

Calls placed through the Telnyx web phone target the routing TeXML
subdomain as `<extension>@<subdomain>.sip.telnyx.com`. Depending on the
callback type, Telnyx may send that value either with the `sip:` scheme or as
a bare SIP URI.

The domain router recognized only the scheme-prefixed form. A bare extension
URI therefore retained its `@` sign and was rejected by the credential-loop
guard before extension lookup. Odoo returned the spoken "Call routing loop
detected" response even though the destination was a valid extension.

The same callback shape also left the call ledger incomplete. Core channel
number extraction recognized only scheme-prefixed SIP URIs, and Telnyx call
progress callbacks could omit fields such as `Direction`; mapping the missing
value to `False` cleared information stored by the initial callback.

## Decision

1. Parse Telnyx routing-subdomain URIs with an optional `sip:` scheme. Strip
   the routing host before applying the credential-loop guard, while keeping
   the guard for real telephony credential usernames.
2. Treat bare `userinfo@host` values as SIP URIs in the provider-neutral
   channel number normalizer. Provider-specific user lookup still decides
   whether the userinfo maps to a PBX extension.
3. When a Telnyx callback omits party, direction, parent, status, or duration
   data for an existing channel, retain the stored value instead of replacing
   it with an empty value.
4. Cover both valid bare extension routing and rejected credential-loop
   routing with regression tests.

## Consequences

- Web-phone calls to extensions and callflows route correctly whether Telnyx
  includes the `sip:` scheme or not.
- Call history keeps the called extension and the technical direction across
  partial call-progress callbacks.
- Credential legs routed back into the TeXML subdomain remain fail-closed and
  cannot create an infinite call loop.
- No schema or data migration is required. Existing malformed call records
  are not rewritten.
