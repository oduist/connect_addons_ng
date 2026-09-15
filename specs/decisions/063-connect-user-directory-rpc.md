# 063 — Colleague directory is an RPC, not a wider record rule

## Problem

`connect.user` carries a record rule, `connect.rule_connect_user_own`, that
limits the `connect.group_user` group to `[('user', '=', user.id)]` — a Connect
user can read their own PBX record and nobody else's.

The softphone needs the opposite. Its colleague search and its live dial-match
both exist so you can reach a coworker by name or extension, and under that
rule they only ever resolve the caller themselves: logged in as extension 101,
searching `100` returned nothing.

## Options considered

1. **Widen `rule_connect_user_own` to all records.** One line, and the search
   starts working. But `connect.user` is where provider modules hang
   credentials: `connect_twilio` adds `password` (the SIP password), plus
   `username` and `sid`. Widening read access hands every colleague's SIP
   password to every Connect user. Rejected outright.

2. **Widen the rule, then hide the sensitive fields behind `groups=`.**
   Restores the search without leaking today's credentials, but it moves the
   security boundary from one rule to a scattering of field attributes, and it
   makes every future field added to `connect.user` by any provider a
   judgement call that has to be got right — silently, with no failing test if
   it is got wrong. Rejected as too easy to erode.

3. **Leave the rule alone and expose a purpose-built directory method.**

## Decision

Option 3. Core `connect.user.search_directory(search_query, limit=10)`:

- refuses anyone outside `connect.group_user` / `connect.group_admin`, the
  same gate `get_user_by_exten_number()` already uses;
- runs `sudo()` and returns a hand-built payload of exactly
  `{id, name, user_id, exten_number}` — never a recordset, never a
  `search_read` the caller can add fields to;
- resolves the extension through `_pbx_number_fields()`, so it is
  provider-agnostic and works in a database with several providers installed.

The record rule is unchanged. A Connect user still cannot read another
`connect.user` record through the ORM; verified — a direct read of a
colleague's `password` still raises `AccessError`.

## Consequences

- The exposed surface is a name and an extension. That is the minimum a dial
  list can be built from, and it is the same information a colleague's caller
  ID already puts on your screen when they ring you.
- Adding a field to `connect.user` cannot widen this by accident. The payload
  is an explicit dict; a new field is invisible here until someone adds it on
  purpose.
- It lives in core rather than in `connect_twilio`, so the other provider
  softphones can adopt it without a second implementation. In this pass only
  `connect_twilio` calls it — the rest still run their own `searchRead` and
  therefore still only find the caller. That is pre-existing behaviour, not a
  regression, but it is the obvious next thing to fix.
- `search_directory` includes the caller. Filtering yourself out would be
  tidier for dialling but confusing for someone checking their own extension,
  and it matches what the list did before.
