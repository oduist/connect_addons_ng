# 004: FreeSWITCH XML-RPC for Odoo-to-FS Communication

> Superseded in part by ADR-043: only the public host remains configurable;
> port, username, password, and TLS verification are now managed internally.

## Problem

Communication between Odoo and FreeSWITCH is pull-only: FreeSWITCH fetches configuration from Odoo via xml_curl. When an admin creates, edits, or deletes a SIP gateway in Odoo, FreeSWITCH continues using stale config until someone manually runs `sofia profile external restart reloadxml` on the FS console.

## Options Considered

1. **mod_xml_rpc** — FreeSWITCH exposes an XML-RPC interface on an HTTP port. Python's standard `xmlrpc.client` can call `freeswitch.api()` to execute any FS CLI command. Simple HTTP basic auth.
2. **ESL (Event Socket Library)** — Full-duplex TCP socket to FreeSWITCH. More powerful (events, real-time control) but requires a persistent connection or per-request TCP setup, plus a third-party Python library (`ESL` or `greenswitch`).
3. **Manual reload** — Document that admins must restart the sofia profile after gateway changes. No code changes needed, but error-prone.

## Decision

Use **mod_xml_rpc** (option 1).

## Rationale

- Uses Python's built-in `xmlrpc.client` — no additional dependencies.
- mod_xml_rpc is already included in FreeSWITCH and only needs to be loaded.
- HTTP-based — works through firewalls and NAT without persistent connections.
- Sufficient for our use case (fire-and-forget API commands after CRUD operations).
- ESL would be over-engineered for occasional reload commands; it makes sense if we later need real-time event processing.

## Implementation

- New settings fields: `freeswitch_xmlrpc_host`, `freeswitch_xmlrpc_port`, `freeswitch_xmlrpc_user`, `freeswitch_xmlrpc_password` on `connect.settings`.
- New method `freeswitch_api(command, args)` on `connect.settings` — catches all exceptions and logs errors without raising, so gateway CRUD is never blocked by FS connectivity issues. (ADR-027 later split the connection logic into a `_freeswitch_rpc()` helper returning a `(result, error)` tuple so the Server Status field can distinguish the failure mode; `freeswitch_api()` keeps the same `response | False` contract.)
- Gateway model (`connect.freeswitch.gateway`) overrides `create`, `write`, `unlink` to call `sofia profile external restart reloadxml` after each operation.
