# ADR-051: Telnyx TeXML callback interpretation and payload safety

## Status

Accepted — 2026-08-16

> Consolidates four rules for reading Telnyx TeXML callbacks — payload
> redaction, recording linkage, bare SIP URI routing with partial payloads, the
> child Dial status and caller identity — that were first drafted as separate
> records. Each is kept below as its own dated section.

## Context

Telnyx TeXML callbacks are not a single stable payload. The same logical event
reaches Odoo with different field names, with or without the `sip:` scheme, with
fields omitted entirely, and with two different call legs described in one
request. Each variant produced a different failure, and each fix is a rule about
how the module reads provider payloads — the kind of rule a later cleanup would
otherwise revert.

Callbacks also carry secret material: the recording callback contains a
short-lived pre-signed `RecordingUrl` whose query parameters are a temporary
download credential.

## Decision 1 — Redact recording URLs in debug output (2026-08-16)

The Telnyx adapters logged complete webhook dictionaries through `connect.debug`,
which persisted the pre-signed download URL long after it was needed.

Raw Telnyx payloads are formatted for debug output through one shared helper. It
recursively replaces `RecordingUrl` — including equivalent key casing and
underscore variants — with `[redacted]`, without mutating the payload used by
business logic. The real URL is still kept on `connect.recording.media_url`;
only debug output is redacted. Existing debug rows age out through the normal
debug cleanup cron and are not migrated.

## Decision 2 — The webhook relation outranks API enrichment (2026-08-16)

The recording callback established the correct `connect.call` and
`connect.channel` relations from its TeXML `CallSid`, then enriched them with the
Telnyx recording API response. That response identifies the leg with
`call_leg_id`, a UUID, while `connect.channel.sid` stores the TeXML `v3:...`
CallSid. The failed lookup returned an empty channel and the following
`data.update()` overwrote valid relations with empty values, so the recording was
created but never appeared on the call.

`telnyx_prepare_data()` may return `call_sid`, `call` and `channel` only when the
API leg identifier resolves to an existing `connect.channel`. Unresolved API
identifiers may enrich recording metadata but can never clear or replace a
relation already established by the webhook.

## Decision 3 — Bare SIP URIs and partial call-progress payloads (2026-08-16)

Web-phone calls target the routing TeXML subdomain as
`<extension>@<subdomain>.sip.telnyx.com`, and Telnyx sends that value either with
or without the `sip:` scheme. The domain router recognized only the
scheme-prefixed form, so a bare extension URI kept its `@` sign, hit the
credential-loop guard and produced a spoken "Call routing loop detected" for a
valid extension. The same callback shape also left the ledger incomplete: core
number extraction required a scheme, and call-progress callbacks omitting fields
such as `Direction` cleared data stored by the initial callback.

1. Parse Telnyx routing-subdomain URIs with an optional `sip:` scheme. Strip the
   routing host before applying the credential-loop guard, while keeping the
   guard for real telephony credential usernames.
2. Treat bare `userinfo@host` values as SIP URIs in the provider-neutral channel
   number normalizer. Provider-specific user lookup still decides whether the
   userinfo maps to a PBX extension.
3. When a Telnyx callback omits party, direction, parent, status or duration data
   for an existing channel, retain the stored value instead of replacing it with
   an empty one.
4. Cover both valid bare extension routing and rejected credential-loop routing
   with regression tests.

## Decision 4 — The child Dial status decides fallback routing (2026-08-16)

A Dial action callback carries both `CallStatus` (the parent PSTN leg) and
`DialCallStatus` (the child destination leg). After an answered SIP destination
hangs up normally, the callback can read `CallStatus=in-progress` together with
`DialCallStatus=completed`. Preferring `CallStatus` treated the successful child
leg as unfinished and advanced the user's fallback chain, so the external caller
heard voicemail after an answered call.

1. The Telnyx user Dial action handler uses `DialCallStatus` as the authoritative
   result of the attempted destination leg.
2. `CallStatus` is used only as a compatibility fallback when `DialCallStatus` is
   absent.
3. A `completed` destination leg terminates the parent leg with `<Hangup/>` and
   never advances to another user callflow step.
4. Only explicit unsuccessful results (`busy`, `no-answer`, `failed`, `canceled`)
   advance the user fallback chain.
5. Missing or unknown results fail closed with `<Hangup/>` instead of starting
   another destination or voicemail.

## Decision 5 — One caller resolution for routing, caller ID and recording (2026-08-16)

Web-phone calls enter the routing TeXML application as an inbound SIP leg, and
the credential URI identifying the PBX user is reported in `Caller`, `From` or
`CallerId` depending on the webhook variant. The routing guard resolved all
variants through `connect.user._telnyx_caller()`, but `originate_external_call()`
repeated the lookup using only `Caller`. With a `From`-only payload the user was
allowed to dial out but was lost before `record_calls` was evaluated, so the
generated `<Dial>` omitted `record` and the call was never recorded.

1. Every Telnyx routing path that needs the originating PBX user resolves the
   caller with `connect.user._telnyx_caller()`.
2. `originate_external_call()` uses that normalized identity for both caller ID
   selection and the user's `record_calls` setting.
3. The outbound routing test suite includes the real Telnyx payload shape where
   the credential URI is in `From` and `Caller` is absent.
4. When recording is enabled, the generated TeXML carries both
   `record="record-from-answer"` and the recording status callback.

## Rejected alternatives

- **Prefer `CallStatus` for fallback routing**: it describes the still-active
  parent leg, not the result needed to decide whether fallback is appropriate.
- **Advance the fallback chain on every result except `completed`**: an unknown
  or incomplete status would ring another endpoint or start voicemail after a
  connected call.
- **Remove fallback routing entirely**: explicit missed-call outcomes still need
  to continue through the configured user callflow.
- **Fall back to the default caller ID and default recording policy when
  `Caller` is absent**: the webhook still identifies the user in `From`, so
  discarding that identity would ignore an explicit per-user setting.
- **Enable recording for every outbound route unconditionally**: administrators
  must be able to disable recording per user.

## Consequences

- New Telnyx debug rows no longer persist temporary recording download
  credentials.
- TeXML recordings stay linked to their calls when the recording API uses a UUID
  leg identifier, while API-only data can still establish a relation when its
  identifier genuinely matches a stored channel SID.
- Web-phone calls to extensions and callflows route correctly with or without the
  `sip:` scheme, and credential legs routed back into the TeXML subdomain remain
  fail-closed against infinite loops.
- Call history keeps the called extension and technical direction across partial
  call-progress callbacks.
- Voicemail stays available for calls that were not connected but can no longer
  start after a caller has spoken to a SIP or web-phone destination; unexpected
  provider statuses end the call safely and are logged.
- Outbound web-phone calls follow the user's recording setting regardless of
  which caller field Telnyx supplies, and routing authorization, caller ID
  selection and recording policy cannot disagree about the originating user.
- No schema or data migration is required by any of these rules. Existing
  malformed call records are not rewritten.
