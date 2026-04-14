# ADR-008: Gateway IP ACL for Unauthenticated Inbound Calls

## Status
Accepted

## Problem
FreeSWITCH external profile has `auth-calls=true`, which sends a 407 Proxy Authentication Required challenge to every incoming INVITE. VoIP providers (e.g., Peoplefone) send INVITEs without SIP credentials — they expect their IP to be trusted. The call is rejected, the provider retries with a new call-id, and the cycle repeats indefinitely.

We need a way to accept inbound calls from known provider IPs without requiring SIP digest authentication, while still requiring auth for SIP endpoint registrations and calls from unknown sources.

## Options Considered

### A. Separate no-auth sofia profile on a different port
Create a second sofia profile without `auth-calls` for provider traffic. Providers would connect on a different port.

- Pro: Clean separation
- Con: Adds operational complexity (two profiles, two ports), providers may not support non-standard ports

### B. ACL whitelist on existing external profile (`apply-inbound-acl`)
Add `apply-inbound-acl` parameter to the external profile pointing to a named ACL list. IPs in the ACL bypass auth; all others go through normal 407 challenge.

- Pro: Single profile, standard FreeSWITCH mechanism, IPs managed per-gateway in Odoo
- Con: Requires IP management (providers must have stable IPs)

### C. Disable `auth-calls` entirely
Set `auth-calls=false` on the external profile.

- Pro: Simplest change
- Con: Removes authentication for all sources — any IP can send calls through the system

## Decision
**Option B** — ACL whitelist via `apply-inbound-acl` on the existing external profile.

## Implementation
- `inbound_ips` Text field on `connect.freeswitch.gateway` model — one IP/CIDR per line
- `config_acl` Jinja2 template generates `acl.conf` with a `gateways` ACL list (default: deny)
- `config_sofia` template includes `<param name="apply-inbound-acl" value="gateways"/>`
- Controller serves `acl.conf` dynamically via xml_curl, always returning the ACL (even if empty)
- Gateway create/write/unlink triggers `reloadacl` when IPs change

## Rationale
This is the standard FreeSWITCH pattern for trusting provider IPs. It keeps a single external profile, requires no additional ports, and integrates cleanly with the existing xml_curl dynamic configuration. The per-gateway IP management in Odoo gives admins a clear UI for whitelisting provider networks.
