# ADR-050: Allow the webhook user to read PBX users

**Status:** Accepted
**Date:** 2026-08-14

## Context

Provider webhook handlers run as the dedicated user in
`connect.user_connect_webhook`. Twilio call completion callbacks can continue a
user call flow by loading the addressed `connect.user` and rendering its next
step. The webhook group had no model access to `connect.user`, so the callback
failed with HTTP 403 after an unanswered or busy dial leg. For example, an
extension-to-extension call could reach the destination but fail when Twilio
requested the destination user's call-action URL.

## Decision

Grant `connect.group_webhook` read-only model access to `connect.user`. Do not
grant create, write, or unlink access. The webhook group has no `connect.user`
record rule, because provider callbacks must be able to resolve any PBX user
addressed by a verified event.

## Consequences

- Verified provider callbacks can read the PBX user required to continue call
  routing.
- The dedicated webhook user still cannot modify PBX user configuration.
- Provider request authentication remains the boundary that protects webhook
  routes from untrusted callers.
