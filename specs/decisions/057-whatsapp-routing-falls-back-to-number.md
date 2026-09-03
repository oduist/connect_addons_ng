# ADR-057: Route inbound WhatsApp calls by the number's destination

**Status:** Accepted
**Date:** 2026-08-19

## Context

Twilio delivers an inbound WhatsApp call through the SIP domain's TwiML
application, so it lands in `connect.twilio.domain.route_call()`. That
function resolved the destination purely from `connect.twilio.exten` and,
finding nothing, answered:

> Whatsapp Extension not found! Please create an extension for this
> Whatsapp number!

A plain PSTN call to the very same number arrives on a different route —
`/twilio/webhook/number` → `connect.twilio.number.route_call()` — which reads
`connect.twilio.number.destination` and reaches the configured user or
callflow. So a number could be fully configured, visibly routed to a user in
the UI, and still reject WhatsApp calls. The two routes disagreed about what
"configured" means.

Note that `found_num` does not mean the same thing on both paths inside
`route_call()`:

- SIP: `To = sip:<dialled>@…` — the number the softphone dialled, an
  **outbound destination**;
- inbound WhatsApp: `To = whatsapp:+<ours>` — **our own number**, the called
  party.

## Decision

Fall back to `connect.twilio.number` in the WhatsApp branch only.

- When no extension matches and the call is WhatsApp, search
  `connect.twilio.number` by `phone_number` and return its `render()`.
- `render()` is the same method the PSTN path uses, so `user`, `callflow` and
  `twiml` destinations behave identically on both routes, and an unconfigured
  number keeps answering "Number not configured".
- An extension still takes precedence; the prompt survives for a number that
  matches neither, with its "extenstion" typo fixed.
- `is_ignored` is not consulted, matching `connect.twilio.number.route_call()`,
  where the flag only governs pushing configuration to Twilio.

The SIP branch is deliberately left alone. There `found_num` is an outbound
destination, so the same fallback would turn dialling one of our own numbers
into a loop back inbound instead of an outbound call.

## Consequences

- A number routed to a user answers WhatsApp calls without a dedicated
  extension, which is what the UI already implied.
- Extensions remain the way to give WhatsApp its own dialplan, distinct from
  the PSTN destination.
- Outbound WhatsApp is untouched: the early return still fires before
  `originate_whatsapp_call()`, leaving that path unreachable from
  `route_call()`. That is a separate question, deliberately out of scope here.
