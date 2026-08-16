# ADR-050: Make Telnyx account reconciliation complete and fail-closed

**Status:** Accepted
**Date:** 2026-08-16
**Relates to:** [ADR-032](032-connect-telnyx-provider.md), [ADR-033](033-connect-telnyx-whatsapp-rcs.md)

## Context

Telnyx list endpoints are paginated. The raw WhatsApp API transport introduced
for sender and template synchronization read only the first page and then
removed local records missing from that incomplete response. An account with
more than one page of resources could therefore lose valid local mirrors and
their local configuration during a routine account sync. Treating a malformed
successful response as an empty list creates the same destructive outcome.

The Number Calls TeXML application is another account-level resource. A plain
Connect user may legitimately trigger its first remote bootstrap through
click-to-call after a module upgrade, but that user intentionally has read-only
access to `connect.telnyx.texml`. Creating the remote application and then
failing to persist its SID leaves the call unsuccessful and may orphan the
remote resource.

## Decision

1. Raw Telnyx collection reads use one shared page-number/page-size helper. The
   helper consumes every page reported by `meta.total_pages` and validates that
   every response contains a list in `data` before returning any records.
2. Destructive reconciliation happens only after the complete collection has
   been fetched successfully. A malformed page or failed request aborts the
   sync without deleting local records. WhatsApp sender records marked **Do not
   sync** are excluded from deletion as well as update.
3. Lookup, creation and SID persistence for the required Number Calls TeXML
   application run on a narrowly scoped `sudo()` recordset. This does not grant
   Connect users general write access to TeXML applications; it only lets the
   provider bootstrap its own mandatory system resource while processing an
   otherwise authorized call.

## Alternatives considered

- **Reconcile the first page only.** Rejected because absence from an incomplete
  page is not evidence that a remote resource was deleted.
- **Treat a missing `data` member as an empty account.** Rejected because a
  schema or provider response change must fail closed before local deletion.
- **Grant Connect users write access to all TeXML applications.** Rejected
  because these are administrator-owned PBX configuration records.
- **Require an administrator to synchronize after every upgrade.** Rejected
  because click-to-call already owns the lazy bootstrap path and can safely
  complete it without widening user permissions.

## Consequences

- WhatsApp synchronization performs additional requests on accounts whose
  resources span multiple pages, but never deletes from a partial snapshot.
- Provider response-shape changes surface as synchronization errors instead of
  being interpreted as an empty account.
- Ordinary Connect users can place calls while the required system TeXML
  application is being initialized, without receiving broader configuration
  access.
