# ADR-027: FreeSWITCH Server Status distinguishes failure modes

**Status:** Accepted
**Date:** 2026-06-02

## Context

The **Server Status** field on `connect.settings` (FreeSWITCH tab) is
populated by the `check_freeswitch_status` button. Its first probe
calls `freeswitch_api('status')`, and on any falsy return the field was
set to the single string `DOWN (unreachable)`.

`freeswitch_api()` returns `False` for several genuinely distinct
failure modes (see ADR-004 — it catches all exceptions and never
raises, so gateway CRUD is never blocked):

1. **Not configured** — no XML-RPC host set; no TCP connection is even
   attempted.
2. **Unreachable** — host configured but the TCP connection fails
   (firewall, port closed, wrong host, DNS).
3. **Auth failed** — host reachable but the credentials are wrong
   (`mod_xml_rpc` returns HTTP 401).
4. **Invalid response** — the server answered but the payload could not
   be parsed (malformed XML, XML-RPC fault).

Collapsing all four into `DOWN (unreachable)` is misleading: each needs
a different operator action (set credentials in Odoo vs. open a port
vs. fix the password vs. check the FS side). The gateway loop in the
same method already classifies its own failures
(`Unreachable` / `Not loaded` / `Parse error`); the top-level status
had simply not caught up.

## Options

1. **Change `freeswitch_api()` to return the reason string on
   failure.** Smallest diff at the call site, but `freeswitch_api()` is
   called from four places (`status`, `show calls count`,
   `sofia xmlstatus`, per-gateway `xmlstatus`), three of which rely on
   the `response | False` contract and would mis-treat a reason string
   (`'AUTH FAILED'`) as a successful response to parse. Rejected — it
   silently breaks the other callers.
2. **Add a low-level helper that returns a structured
   `(result, error)` tuple, and keep `freeswitch_api()` as a thin
   wrapper over it.** The three parsing call sites keep the
   `response | False` contract unchanged; only the status probe opts in
   to the richer result. Chosen.
3. **Probe connectivity separately (e.g. a raw socket connect) before
   calling the API.** Duplicates connection logic, races against the
   real call, and cannot distinguish auth failure from a parse error.
   Rejected.

## Decision

**Option 2.** New `connect.settings._freeswitch_rpc(command, args)`
returns `(result, error)`:

- success → `(response_string, None)`;
- failure → `(None, error)` where `error` is one of the bare,
  operator-facing strings `NOT CONFIGURED`, `UNREACHABLE`,
  `AUTH FAILED`, `INVALID RESPONSE`.

Mapping:

| Condition | `error` |
|-----------|---------|
| `freeswitch_xmlrpc_host` empty | `NOT CONFIGURED` |
| `xmlrpc.client.ProtocolError`, `errcode == 401` | `AUTH FAILED` |
| `xmlrpc.client.ProtocolError`, other code | `INVALID RESPONSE` |
| `OSError` (`socket.timeout`, `ConnectionError`, `ConnectionRefusedError`, `socket.gaierror`) | `UNREACHABLE` |
| any other exception (`xmlrpc.client.Fault`, XML parse, …) | `INVALID RESPONSE` |

`freeswitch_api()` becomes
`result, error = self._freeswitch_rpc(...); return result if error is None else False`
— its contract is unchanged, so the calls/registrations/gateway code
paths are untouched.

`check_freeswitch_status()` calls `_freeswitch_rpc('status')` for the
first probe and writes the bare `error` string straight into
`freeswitch_status`.

### Why bare strings, not `DOWN (...)`

The status field is the final, operator-facing value; the reason **is**
the status. Prefixing every failure with `DOWN` is redundant and, for
`NOT CONFIGURED`, inaccurate (the server may well be up — Odoo just was
never told how to reach it). So the field now shows `UNREACHABLE`,
`AUTH FAILED`, etc. directly.

## Consequences

- **Display change.** `DOWN (unreachable)` is replaced by one of
  `NOT CONFIGURED` / `UNREACHABLE` / `AUTH FAILED` / `INVALID RESPONSE`.
  Read-only field, no stored semantics depend on the old string.
- **`freeswitch_api()` contract is preserved** — the three other
  callers and any external callers see no behavioural change.
- **New `import socket`** in `connect_freeswitch/models/settings.py`
  for the `socket.timeout` / `socket.gaierror` documentation of intent
  (both are `OSError` subclasses, caught via `except OSError`).
- **Docs updated** — `docs/admin/freeswitch-setup.md` gains a Server
  Status reference table mapping each value to the action to take.

## References

- ADR-004 — FreeSWITCH XML-RPC; established the
  catch-all-and-return-`False` contract this ADR refines.
- GitHub issue #40 — "`DOWN (unreachable)` is misleading — collapses
  three distinct failure modes".
- `connect_freeswitch/models/settings.py` — `_freeswitch_rpc()`,
  `freeswitch_api()`, `check_freeswitch_status()`.
