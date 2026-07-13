# ADR-024: Normalize caller ID to E.164 before partner matching

## Status
Accepted

## Context

Different telephony providers deliver the caller ID in different formats.
A Swiss inbound trunk may surface `0313808316`; a Twilio webhook delivers
`+41313808316`; an old PBX may even send `0041313808316`. The partner
database, on the other hand, is typically normalized via Odoo's
`phone_validation` to one canonical representation (E.164).

Two pieces in `connect` blocked partner matching for non-E.164 caller IDs:

1. `connect/models/channel.py::_find_partner` only called
   `Partner.get_partner_by_number()` when the relevant side of the call
   started with `+`. A local-format number like `0313808316` was dropped
   on the floor — `partner` stayed `NULL` on the channel/call.
2. `connect/models/res_partner.py::get_partner_by_number` then passed the
   raw string to `phone_mobile_search`. `phone_mobile_search` has two
   code paths internally:
   - if the input starts with `+`/`00`, it strips the prefix and matches
     against both `+` and `00` variants in the DB;
   - otherwise it strips non-digits and matches the stripped form
     literally.
   The two paths share no normalized representation, so `0313808316`
   never matches a stored `+41313808316` and vice versa.

Concrete repro: Call 215 had caller `0313808316`, partner 9 had phone
`0313808316`, partner field on the call was `NULL`. After we normalize
both sides to E.164 the same partner matches in both directions.

## Decision

Two narrow changes, both in `connect/`:

1. **`_find_partner`**: drop the `startswith('+')` guards. The method
   keeps its job of picking the external side of the call
   (caller vs. called, by `*_pbx_user` flags and direction), but the
   format check is delegated entirely to `get_partner_by_number` — that
   is the single place that owns "given a number string, which partner
   is it".

2. **`get_partner_by_number`**: keep the first
   `phone_mobile_search = number` search (this still catches the easy
   cases where the provider already gives E.164 or the DB happens to
   store the local form). If it returns nothing, fall back to a second
   search with the number normalized to E.164 via the existing
   `format_number(self, number, country)` helper. Country comes from the
   main company (`res.company.browse(1).country_id.code`) — that is the
   only stable source in webhook context, where `self` is the empty
   `res.partner` recordset. Existing deduplication logic below is left
   untouched.

Putting the normalization inside `get_partner_by_number` (rather than
inside `_find_partner`) means every other caller of the lookup — webhook
handlers, public API endpoints, the SMS composer, partner smart buttons —
inherits the same fallback for free.

## Alternatives considered

- **Normalize at write time on `res.partner.phone`.** That would fix new
  rows but does not help existing data, and would still leave incoming
  caller IDs in mixed formats. Rejected — narrower fix at the lookup
  point handles both directions without a data migration.
- **Always normalize before the first search and skip the original-number
  search.** Rejected — `format_number` is best-effort; if parsing fails
  it returns the original number anyway, so the "try original first" path
  is essentially free and protects us against `format_number` corner
  cases (e.g. internal short codes that happen to be in the DB verbatim).
- **Loop over a list of formats (E.164, national, international,
  significant-only).** Over-engineered for the observed bug. The
  `phone_mobile_search` index already covers `+`/`00` prefix variation;
  the only missing case is "stored in E.164, looked up in local format",
  which one extra search resolves.

## Risks / open items

- **Multi-company deployments.** Using `res.company.browse(1)` ties the
  country to the main company. For single-tenant FreeSWITCH/Twilio
  deployments this is correct; multi-company setups with regional caller
  IDs would need `self.env.company` (or per-trunk country). Not in scope
  for this fix — flagged for follow-up if it becomes a real problem.
- **Internal short codes (`100`, `101`, …).** With the `startswith('+')`
  guard removed, internal extension numbers also reach
  `get_partner_by_number`. The `_find_partner` guards above
  (`caller_pbx_user` / `called_pbx_user`) already steer the lookup to
  the external side of the call, so internal-to-internal calls do not
  reach the lookup with an extension number.

## Verification

Reproduced on the `fs19` oduflow environment with template `fs19`
(includes partner 9 with phone `0313808316`):

- Inbound call with caller `0313808316` → `connect.call.partner = 9`.
- Inbound call with caller `+41313808316` against a partner stored as
  `0313808316` → also matched.
- Inbound call with caller `+41…` against partner stored as `+41…` —
  unchanged (first search still hits).

## Tests

Covered by tests in `connect/tests/`. The regression should cover both
directions (E.164 in DB, local in caller; and local in DB, E.164 in caller)
plus the no-match case.

## Cross-branch backport

Per the cross-branch versioning rules in `CLAUDE.md`, the same fix ports
to the `18.0` branch with the aligned tail version. Backport ships as a
separate PR.
