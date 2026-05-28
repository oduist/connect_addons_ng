# ADR-021: Drop the validated-only filter from the Twilio user form picker

## Status
Accepted

## Context

ADR-019 dropped the Twilio-only `status='validated'` leaf from the core
`connect.user.outgoing_callerid` domain and restored it in
`connect_twilio` via view-inheritance:

```xml
<xpath expr="//field[@name='outgoing_callerid']" position="attributes">
    <attribute name="domain">
        ['|', ('status', '=', 'validated'),
              ('callerid_type', '=', 'number')]
    </attribute>
</xpath>
```

ADR-020 then removed the remaining `callerid_type='number'` filter from
the core domain so FreeSWITCH users could select any caller ID.

The Twilio view filter is now the only remaining picker restriction.
In practice, Twilio installations want the same lenient behavior the
core form already provides: show every caller ID record and let the user
pick, without hiding non-validated CallerIDs behind a view-level filter.
The Twilio API does its own validation at call time, so the safety net
the filter was supposed to provide is not load-bearing — and hiding
records is more confusing than helpful when administrators are still
setting them up.

## Decision

Remove the `outgoing_callerid` domain override from
`connect_twilio/views/user_views.xml` entirely. The Twilio user form now
inherits the unfiltered picker from core.

## Consequences

- Twilio administrators see all `connect.outgoing_callerid` records in
  the picker, including CallerIDs whose validation is still in progress.
  Selecting an unverified CallerID will be rejected by Twilio at call
  time — the same UX as picking an invalid number directly via the API.
- `connect_twilio/views/user_views.xml` no longer references the
  Twilio-only `status` field on the picker; the only Twilio-specific
  field on the form remains the `domain` / `twilio_edge` pair added next
  to it.
- The Twilio override introduced in ADR-019 is fully reverted; ADRs 019,
  020, and 021 together end with no picker filter on either side.

## Cross-branch backport

Per `CLAUDE.md` versioning rules, the same change ports to the `18.0`
branch with aligned tail versions (`18.0.3.1.5` for `connect`,
`18.0.1.1.3` for `connect_twilio`). The backport ships as a separate PR.
