# ADR-050: Keep the Asterisk channel hint consistent in endpoint editors

**Status:** Accepted
**Date:** 2026-08-14

## Context

An Asterisk endpoint can be created either from its standalone form or inline
on the Connect User form. The standalone form showed `PJSIP/101` as the
expected Asterisk Channel format, while the inline list had no placeholder.
This made the same field less discoverable in the most direct user workflow.

## Decision

Use `PJSIP/101` as the `asterisk_channel` placeholder in both endpoint editors.
The value remains an example only; validation and stored data are unchanged.

## Consequences

- Users see the expected channel syntax when adding an endpoint from either UI.
- No model, security, or migration change is required.
