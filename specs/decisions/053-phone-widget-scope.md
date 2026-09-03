# ADR-053: Apply the phone widget to actionable phone values

**Status:** Accepted
**Date:** 2026-08-14

## Context

Connect displays phone numbers in messaging, call history, user routing, and
business-record views. Several of these Char fields were rendered as plain
text, so users did not get Odoo's consistent phone formatting and click-to-call
behavior. The same repository also contains provider configuration catalogs,
technical identifiers, extension numbers, relation fields, and search inputs
where the phone widget is either undesirable or ineffective.

## Decision

Use `widget="phone"` for actionable phone values in these UI surfaces:

- message ledger list and form views;
- WhatsApp and RCS recipient composer fields;
- call, channel, and recording list/form views, including embedded history;
- the call transfer destination;
- external user-routing phone numbers;
- UTM source and related partner phone/mobile values shown on business forms.

Do not add the widget to provider number and caller-ID configuration catalogs,
extension values, Many2one relations, technical identifiers, URI-like channel
destinations, or search-view fields.

## Consequences

- Operational phone values behave consistently across messaging and calling
  workflows.
- Historical and related business-record numbers become directly actionable.
- Provider configuration screens remain plain data-entry and administration
  surfaces.
- Search semantics and non-PSTN identifiers are unchanged.
