# ADR-059: Validate the Twilio signature against the POST body only

**Status:** Accepted
**Date:** 2026-08-21

## Context

Twilio computes `X-Twilio-Signature` over the request URL — query string
included — with the POST body parameters appended, sorted, name and value
concatenated. `RequestValidator.validate(url, params, signature)` expects
exactly those POST parameters in `params`.

`ConnectTwilioController.check_signature(data)` was called as
`check_signature(kw)` from every webhook route, and Odoo's `**kw` merges the
query string into the route kwargs. For a URL with no query string the two
sets are identical and validation passed, which is why this went unnoticed:
every Twilio webhook URL in the module was query-free.

The `<Dial>` action URL stopped being query-free when the sequential-ring
walk started carrying its state there:

```
/twilio/webhook/connect.user/call_action/2?done_callflows=3#e=ashburn
```

`done_callflows` then reached the validator twice — once inside the signed
URL, once as a phantom POST parameter — so the signature never matched and
the route answered its rejection TwiML:

> `<Response><Say>Invalid Twilio request!</Say></Response>`

That webhook fires when a dialed leg ends without being answered, so with
`twilio_verify_requests` enabled **every rejected or unanswered call spoke
"Invalid Twilio request!" to the caller** instead of ringing the next device.

## Decision

`check_signature()` takes no arguments and reads the parameters itself:
`request.httprequest.form` for a POST, `{}` otherwise (Twilio puts everything
in the URL for a GET). All thirteen call sites drop their `kw` argument.

The fix is at the validation layer rather than at the action URL, because the
defect belongs to the layer: any future webhook URL carrying a query
parameter would have hit it, and each one would have failed silently, in a
different place, at call time.

## Consequences

- URLs with a query string validate; the `done_callflows=` marker works as
  designed and an unanswered leg advances to the next device.
- Validation is not weakened: a signature computed over a different URL or
  different body is still rejected. `test_webhook_signature.py` covers a
  signed URL with a query string, one without, and a forged signature.
- The `#e=<edge>` fragment is unaffected — a fragment is never sent to the
  server and Twilio does not sign it.
