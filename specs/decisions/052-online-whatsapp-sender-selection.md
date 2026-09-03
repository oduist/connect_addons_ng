# ADR-052: Select only online Twilio WhatsApp senders

**Status:** Accepted
**Date:** 2026-08-14

## Context

The WhatsApp composer limits its sender field to synchronized senders whose
status is `ONLINE`, but its default value comes from
`connect.whatsapp_sender.get_default_sender()`. That method previously returned
a user's preferred sender, the globally default sender, or the first sender
without checking its current status. A stale or sandbox sender could therefore
be injected as the default even though it was excluded from the field domain.
The same resolver is also used for WhatsApp voice calls.

## Decision

Apply the availability domain (`no_sync = False`, `status = ONLINE`) inside
`get_default_sender()` at every selection stage: user preference, global
default, and fallback. Apply the same domain to the per-user WhatsApp sender
field so administrators cannot newly assign an unavailable sender.

If no online synchronized sender exists, return no sender and let the calling
workflow report that sender configuration is required.

## Consequences

- Composer defaults and WhatsApp calls cannot silently use offline senders.
- An offline personal or global default sender is skipped in favor of the next
  online candidate.
- Historical sender records remain available for reporting and templates, but
  cannot be selected for new user assignments or outgoing operations.
