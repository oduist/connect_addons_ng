# ADR-019: `connect.user.outgoing_callerid` domain — provider boundary fix

## Status
Accepted

## Context

GitHub issue [#88](https://github.com/oduist/connect_addons_ng/issues/88).

The core model `connect.user` defined the `outgoing_callerid` Many2one
with a domain that referenced a Twilio-only field:

```python
# connect/models/user.py (before)
outgoing_callerid = fields.Many2one(
    'connect.outgoing_callerid', ondelete='set null',
    domain=['|', ('status', '=', 'validated'),
            ('callerid_type', '=', 'number')])
```

The `status` field is added to `connect.outgoing_callerid` only by
`connect_twilio` (`connect_twilio/models/outgoing_callerid.py:16`). On a
FreeSWITCH-only deployment (or any deployment without `connect_twilio`)
the ORM raises `ValueError: Invalid field connect.outgoing_callerid.status
in leaf ('status', '=', 'validated')` whenever the domain is evaluated —
e.g. when opening the user form or the field's dropdown. The
`connect.user` form was therefore unusable for FreeSWITCH-only users.

This also broke a core architectural rule (see `CLAUDE.md` /
`specs/architecture.md`): **the `connect` core never references
provider-specific fields or concepts**. `status` describes the Twilio
Outgoing CallerID validation lifecycle; it does not exist in the
provider-agnostic data model.

## Decision

1. **Drop the `status` leaf from the core domain.** The core domain on
   `connect.user.outgoing_callerid` is now provider-agnostic:

   ```python
   outgoing_callerid = fields.Many2one(
       'connect.outgoing_callerid', ondelete='set null',
       domain=[('callerid_type', '=', 'number')])
   ```

2. **Restore the validated-only filter in Twilio via view-inheritance.**
   `connect_twilio/views/user_views.xml` overrides the field's `domain`
   attribute on the form so that, when Twilio is installed, the picker
   shows only validated outgoing CallerIDs or DID numbers:

   ```xml
   <xpath expr="//field[@name='outgoing_callerid']" position="attributes">
       <attribute name="domain">
           ['|', ('status', '=', 'validated'),
                 ('callerid_type', '=', 'number')]
       </attribute>
   </xpath>
   ```

## Alternatives considered

- **Declare a no-op `status` field in core.** Rejected — leaks a
  Twilio-specific concept into the provider-agnostic layer, the exact
  thing the architecture forbids.
- **Compute the domain dynamically in Python.** Rejected — needless
  complexity for a single attribute. Odoo's `position="attributes"` is
  the idiomatic extension point.
- **Drop the domain altogether.** Rejected — the Twilio UX needs to hide
  unverified caller IDs from the picker, otherwise users can select
  records Twilio will reject at call time.

## Cross-branch backport

Per `CLAUDE.md` versioning rules, the same change must be ported to the
`18.0` branch with aligned tail versions (`18.0.3.1.3` for `connect`,
`18.0.1.1.2` for `connect_twilio`). The backport ships as a separate PR.

## Consequences

- FreeSWITCH-only deployments can open the `connect.user` form and
  select an outgoing caller ID.
- Twilio deployments preserve the previous filter — no UX regression in
  the picker.
- The reverse-domain restriction now lives in view metadata, not in the
  model, mirroring the rest of the Twilio extension surface (extra
  fields are added via `_inherit`, extra UI via view inheritance).
