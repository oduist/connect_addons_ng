# ADR-050: Keep Telnyx sync error notifications visible

**Status:** Accepted
**Date:** 2026-08-15

## Context

Telnyx account sync treats unavailable optional WhatsApp/RCS resources and an
invalid imported AI Assistant configuration as non-fatal. Odoo reports these
failures with warning notifications and continues the rest of the sync.

Those notifications used the default non-sticky behavior, so they disappeared
automatically before an administrator could reliably read or copy the provider
error. The successful completion notification could then make the partial
failure even easier to miss.

## Decision

Send non-fatal Telnyx synchronization error notifications with `sticky=True`:

- optional WhatsApp Sender, WhatsApp Template, and RCS Agent sync failures;
- imported AI Assistant configurations that cannot be pushed back to Telnyx.

Keep successful synchronization and informational notifications non-sticky.
Existing exceptions that abort synchronization remain `ValidationError`
dialogs and do not need notification changes.

## Consequences

- Administrators must explicitly dismiss synchronization warnings and have
  enough time to inspect the provider error.
- A partially successful account sync can still finish, but its failed optional
  steps remain visible alongside the completion notification.
- Tests assert the sticky flag on both synchronization warning paths.
