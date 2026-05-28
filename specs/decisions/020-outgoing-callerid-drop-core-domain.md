# ADR-020: Drop the `callerid_type='number'` domain from `connect.user.outgoing_callerid`

## Status
Accepted

## Context

ADR-019 fixed the immediate crash on FreeSWITCH-only deployments by
removing the Twilio-only `status='validated'` leaf from the core domain.
The remaining domain was:

```python
# connect/models/user.py (post-019)
outgoing_callerid = fields.Many2one(
    'connect.outgoing_callerid', ondelete='set null',
    domain=[('callerid_type', '=', 'number')])
```

`callerid_type` itself is a core selection with two values:
`outgoing_callerid` ("CallerID") and `number` ("DID Number"). Restricting
the user form picker to `number` was a leftover from the original
Twilio-shaped domain: in Twilio, unverified CallerIDs cannot be used as
outgoing identity, so the picker hid them and exposed DID numbers
unconditionally. That filter does not belong in the provider-agnostic
core — for FreeSWITCH (and any other backend that does not differentiate
between CallerID and DID Number), a user must be able to pick *any*
`connect.outgoing_callerid` record.

## Decision

Drop the domain attribute entirely from the core field:

```python
outgoing_callerid = fields.Many2one(
    'connect.outgoing_callerid', ondelete='set null')
```

The Twilio view override introduced in ADR-019 stays as-is and continues
to filter the picker in Twilio installations:

```xml
<xpath expr="//field[@name='outgoing_callerid']" position="attributes">
    <attribute name="domain">
        ['|', ('status', '=', 'validated'),
              ('callerid_type', '=', 'number')]
    </attribute>
</xpath>
```

## Alternatives considered

- **Keep the `callerid_type='number'` filter in core.** Rejected — it
  has no provider-agnostic justification and was actively blocking
  FreeSWITCH users from selecting non-DID caller IDs they had defined.
- **Move the filter into FreeSWITCH via view-inheritance.** Rejected —
  FreeSWITCH has no reason to hide CallerID-type records; doing so would
  just reintroduce the same problem under a different module name.

## Cross-branch backport

Per `CLAUDE.md` versioning rules, the same change must be ported to the
`18.0` branch with aligned tail version (`18.0.3.1.4` for `connect`).
The backport ships as a separate PR.

## Consequences

- FreeSWITCH (and any provider-agnostic deployment) can now assign any
  `connect.outgoing_callerid` record to a user, regardless of
  `callerid_type`.
- Twilio installations are unaffected — the Twilio user-form view still
  restricts the picker to validated CallerIDs or DID numbers.
- Core remains free of provider-specific filtering, in line with the
  architecture rule that drove ADR-019.
