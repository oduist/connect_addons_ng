# 040 — Telnyx web phone call-failure notifications

## Status

Accepted

## Context

When the Telnyx account is billing-blocked (balance exhausted), Telnyx
rejects every call origination on the account with
`404 Not found D19` / hangup cause `UNALLOCATED_NUMBER` **before** any
TeXML routing happens. No webhook reaches Odoo, no CDR is written on the
Telnyx side; the only trace is the hangup cause delivered to the WebRTC
client. The web phone simply returned to the keypad, so users could not
tell a blocked account from a wrong number, a busy callee or a network
problem (live debugging session, 2026-07-16: internal 100 → 101 calls
"just dropped" while the account balance was −$0.01).

Other pre-answer failures (busy, rejected, invalid number) were equally
silent: `_onTelnyxNotification` handled `hangup`/`destroy` only to tear
the session down.

## Decision

Surface every unanswered outbound-call failure as an Odoo notification,
and confirm the balance case server-side (option B below).

1. **Client (`phone.js`)** — in the `hangup`/`destroy` branch of
   `_onTelnyxNotification`, when the session was never accepted and the
   cause is not a user-initiated teardown (`ORIGINATOR_CANCEL`,
   `NORMAL_CLEARING`), show a warning notification with a
   human-readable cause mapped from `call.cause` / `call.sipCode`
   (`USER_BUSY` → busy, `CALL_REJECTED` → rejected,
   `UNALLOCATED_NUMBER` / `INVALID_NUMBER_FORMAT` → number not found,
   otherwise a generic "Call failed: <cause> (SIP <code>)").
2. **Server (`connect.settings.telnyx_check_call_failure()`)** — when
   the failure looks like the billing case (`sipCode == 404` or cause
   `UNALLOCATED_NUMBER`), the client additionally calls this model
   method. It fetches `GET /v2/balance` with the account API key
   (`sudo`), and when `available_credit <= 0` returns
   `{'balance_blocked': True, 'message': ...}`; the client then shows a
   sticky `danger` notification naming the real cause. Members of
   `connect.group_admin` get the actual balance figure in the message;
   plain users get the message without amounts. API errors are
   swallowed (logged via `connect.debug`) and reported as
   `balance_blocked: False` so the generic cause notification still
   stands.

## Options considered

- **A. Pure client-side mapping** — detect the billing case from the
  `D19` suffix in `sipReason`. No server round-trip, but `Dxx`
  diagnostic codes are undocumented internals; a format change would
  make the phone lie about the cause. Rejected.
- **B. Client mapping + server balance confirmation on 404 (chosen)** —
  one RPC + one Telnyx API call, only when a call actually failed with
  the ambiguous 404 cause; the balance message is verified against the
  API before being shown.
- **C. Server-driven cause resolution for every failure** — an RPC per
  hangup (including ordinary busy) with no added value over B. Rejected.

## Consequences

- The diagnostic TEMP commit `ba2b9f7` (console.log of the hangup
  cause) is superseded and reverted by this change.
- `telnyx_check_call_failure` is callable by `connect.group_user`; it
  exposes only a boolean + message (amounts admin-only), never the API
  key or raw API payloads.
- The cause mapping lives in the Telnyx phone widget only; other
  provider phones (Twilio/Verto/JsSIP) have their own error surfaces,
  so the ADR-031 copy-in-sync rule does not apply.
