# ADR-024: System-wide default DID fallback for FreeSWITCH outbound CallerID

## Status
Accepted

## Context

ADR-021 wired `connect.user.outgoing_callerid` into both FreeSWITCH
origination paths:

- Odoo click-to-call — `connect_freeswitch/models/call.py:originate_call()`
  sets the b-leg `origination_caller_id_number`.
- UA-originated (SIP/Verto → PSTN) — `connect_freeswitch/models/outgoing_route.py:generate_dialplan()`
  overrides `effective_caller_id_number` in the `dialplan_outgoing_route`
  template.

Both paths, however, only honoured the **per-user** CallerID. When a user
had no `outgoing_callerid` assigned, they fell back straight to the
**extension number**. The Twilio integration instead falls back to the
**system-wide default** — the `connect.outgoing_callerid` record flagged
`is_default=True` (`connect_twilio/models/domain.py:565-573`,
`callflow.py:77-78`). Issue #96 lists this default fallback explicitly
under "Expected Behavior":

> A system-wide default fallback DID is used when no per-user number is
> assigned.

So FreeSWITCH behaviour diverged from Twilio and left issue #96 only
partially resolved.

`connect.outgoing_callerid.is_default` is a core field; the model's
`_reset_default` constraint guarantees at most one record is the default.

## Decision

Insert the system-wide default DID into the resolution order of both
FreeSWITCH origination paths:

**per-user `outgoing_callerid` → system default (`is_default=True`) → extension**

1. `call.py:originate_call()` (external branch) searches
   `connect.outgoing_callerid` for `is_default=True` and uses its
   `number` between the per-user number and the extension.
2. `outgoing_route.py:generate_dialplan()` resolves the effective
   `connect.outgoing_callerid` record (per-user, else default) and feeds
   its `number` / `friendly_name` into the dialplan template. When neither
   exists, `cid_num` stays empty and the template emits no override, so the
   directory-seeded extension stands — preserving prior behaviour and
   leaving internal calls untouched.

The lookup is inlined at both sites (a one-line `search`) rather than
extracted into a core helper. This matches the style already established
by the per-user fix (ADR-021 reads the field directly in FreeSWITCH) and
by Twilio (which inlines the same `is_default` search in `domain.py` and
`callflow.py`). It keeps the change confined to `connect_freeswitch` — no
`connect` core change and no `connect` manifest bump.

## Alternatives considered

- **Add a resolver helper to core (`connect.user` or
  `connect.outgoing_callerid`) and call it from both modules.** Rejected
  for now — it couples a FreeSWITCH bug fix to a `connect` core change and
  bump, for a one-line lookup that the codebase already inlines elsewhere.
  Worth revisiting only if a third consumer appears.
- **Seed the default into the directory template `cid_num`.** Rejected for
  the same reason ADR-021 rejected it — a directory-level default leaks the
  PSTN DID into internal extension-to-extension calls.

## Cross-branch backport

Per `CLAUDE.md` versioning rules, the same fix ports to the `18.0` branch
with the aligned tail version (`18.0.1.10.2` for `connect_freeswitch`). The
backport ships as a separate PR.

## Consequences

- A user with no per-user CallerID now presents the system default DID on
  outbound PSTN calls (both click-to-call and desk-phone/Verto), matching
  Twilio.
- With neither a per-user nor a default CallerID configured, behaviour is
  unchanged: the extension number is used.
- Internal extension-to-extension calls are unaffected — the override lives
  only on the outbound route / b-leg.
- Issue #96 is fully resolved: per-user DID, system default fallback, and
  Twilio-consistent behaviour are all in place.
