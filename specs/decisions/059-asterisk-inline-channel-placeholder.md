# ADR-059: Keep Asterisk endpoint hints consistent across editors

**Status:** Accepted
**Date:** 2026-08-14

## Context

An Asterisk endpoint can be created either from its standalone form or inline
on the Connect User form. The standalone form showed `Endpoint Name` and
`PJSIP/101` as input hints, while the inline list had no placeholders. This
made the same fields less discoverable in the most direct user workflow.

## Decision

Use `Endpoint Name` for `name` and `PJSIP/101` for `asterisk_channel` in both
endpoint editors. The values remain examples only; validation and stored data
are unchanged.

## Consequences

- Users see the expected name and channel formats when adding an endpoint from
  either UI.
- No model, security, or migration change is required.
