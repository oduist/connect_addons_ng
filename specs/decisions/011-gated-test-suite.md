# ADR-011: Gated Test Suite Architecture

## Status
Superseded by ADR-034

## Context
This ADR previously described a private external test repository wired into the
addons tree. That design caused recurring branch and delivery friction.

## Superseded Decision
Do not use this architecture for current development. Tests now live directly
inside the owning Odoo module and are committed with the implementation they
verify. See ADR-034 for the active policy.
