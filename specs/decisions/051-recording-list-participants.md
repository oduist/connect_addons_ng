# ADR-051: Show recording participants in the recordings list

**Status:** Accepted
**Date:** 2026-08-16

## Context

The core recordings list shows call identifiers, phone numbers, duration,
summary, and date, but it does not expose the linked partner or Odoo users.
Administrators therefore have to open individual recordings to identify the
business contact and internal participants.

`connect.recording` already stores a partner and selected caller/called user
references. Some providers, however, create the recording from a call or
channel without copying `called_user`, while the shared `connect.call` ledger
still contains its caller, called, and answered users.

## Decision

- Add a computed `connect.recording.users` field that combines the recording's
  user references with all Odoo user participants available on its linked
  call.
- Add `partner` and `users` to the core recordings list as optional columns
  shown by default.
- Render `users` with the many-to-many tags widget so multiple participants
  remain readable in one column.

## Consequences

- Recording participants are visible without opening each record.
- The column works consistently for incoming, outgoing, and provider-specific
  recording ingestion paths.
- The field is computed and not stored, so it introduces no duplicated
  participant state or migration backfill.
