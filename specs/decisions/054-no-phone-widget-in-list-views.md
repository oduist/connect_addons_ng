# ADR-054: Keep the phone widget out of list views

**Status:** Accepted
**Date:** 2026-08-16

## Context

ADR-053 applied Odoo's `phone` widget to actionable phone values in both form
and list views. In lists, the widget adds dialing and messaging actions to
every phone cell. This makes dense operational tables noisier and changes the
expected row interaction even when users only need to scan the number.

## Decision

Render phone values as plain fields in every `<list>` view, including embedded
One2many lists such as call channels and project/task recording histories.

Keep `widget="phone"` on phone values in form and wizard views, where the user
is focused on one record or explicitly entering a destination. Provider
configuration catalogs, search views, extensions, relations, and technical
identifiers remain outside the phone-widget scope established by ADR-053.

This decision supersedes only the list-view portion of ADR-053.

## Consequences

- Lists remain compact and retain normal row-navigation behavior.
- Phone numbers in lists are readable but do not expose inline dial/message
  actions.
- Forms and composers continue to provide phone formatting and click-to-call
  behavior where it is useful.
