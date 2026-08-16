# 052 — Telnyx recording webhook safety and linkage

## Status

Accepted

## Context

Telnyx TeXML recording callbacks carry a short-lived pre-signed
`RecordingUrl`. The Telnyx adapters logged complete webhook dictionaries via
`connect.debug`, which persisted the URL and its temporary authorization query
parameters even though the URL was needed only for recording processing.

The recording callback also established the correct `connect.call` and
`connect.channel` relations from its TeXML `CallSid`, then enriched the values
with the Telnyx recording API response. That response identifies the leg with
`call_leg_id`, a UUID, while `connect.channel.sid` stores the TeXML `v3:...`
CallSid. The failed UUID lookup returned an empty channel and the subsequent
`data.update()` replaced the valid webhook relations with empty values. The
recording was created but did not appear on the call.

## Decision

1. Format raw Telnyx webhook payloads for debug output through one shared
   helper. It recursively replaces `RecordingUrl` (including equivalent key
   casing or underscore variants) with `[redacted]` without mutating the
   original payload used by business logic.
2. Treat the recording webhook's TeXML `CallSid` relation as authoritative.
   `telnyx_prepare_data()` may return `call_sid`, `call`, and `channel` only
   when the API leg identifier resolves to an existing `connect.channel`.
   Unresolved API identifiers enrich recording metadata but cannot clear or
   replace a relation already established by the webhook.
3. Keep the actual recording URL on `connect.recording.media_url`; only debug
   output is redacted. Existing debug rows age out through the normal debug
   cleanup cron and are not migrated.

## Consequences

- New Telnyx debug rows no longer persist temporary recording download
  credentials.
- TeXML recordings remain linked to their calls when the recording API uses a
  UUID leg identifier instead of the TeXML CallSid.
- API-only recording data can still establish a relation when its leg
  identifier genuinely matches a stored channel SID.
- No schema or data migration is required.
