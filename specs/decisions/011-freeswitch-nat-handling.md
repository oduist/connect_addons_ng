# 011 - FreeSWITCH NAT Handling for SIP Phones

## Problem

SIP phones registering from behind NAT advertise their private IP (e.g., `192.168.0.197`) in the SIP Contact header. FreeSWITCH stores this as the registration contact address. When an inbound call arrives, FreeSWITCH sends the INVITE to the private IP, which is unreachable from the server. The INVITE retransmits with exponential backoff (1s, 2s, 4s, 8s) until timeout.

Outgoing calls from the same phone work because the phone initiates the UDP packet, opening a NAT pinhole that allows the reply path.

## Options Considered

### A. Per-user `sip-force-contact` in directory template

Add `<param name="sip-force-contact" value="NDLB-connectile-dysfunction"/>` to each user's directory entry. This rewrites the contact on a per-user basis.

**Pros:** Granular control per endpoint.
**Cons:** Requires template change and applies universally anyway — no use case for per-user NAT policy.

### B. Profile-level NAT parameters (chosen)

Add NAT detection and contact rewriting parameters to the sofia profile settings.

**Pros:** Applies uniformly to all registrations, no per-user config, works with the single-profile architecture (ADR-003). Standard FreeSWITCH approach for internet-facing profiles.
**Cons:** Cannot disable NAT handling for specific users (not needed in practice).

### C. External SIP proxy / Session Border Controller

Deploy a SIP ALG or SBC (e.g., Oduist Oduist, Kamailio) in front of FreeSWITCH to handle NAT traversal.

**Pros:** Full control over NAT traversal, topology hiding.
**Cons:** Significant complexity, additional infrastructure, overkill for this problem.

## Decision

Option B — profile-level NAT parameters in the `config_sofia` template.

Four parameters added to the external profile:

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `aggressive-nat-detection` | `true` | Compares Via header IP with packet source IP to detect NAT |
| `NDLB-received-in-nat-reg-contact` | `true` | Rewrites stored Contact URI with received (public) IP:port |
| `nat-options-ping` | `true` | Sends periodic OPTIONS to keep NAT pinholes open |
| `apply-nat-acl` | `rfc1918.auto` | Auto-applies NAT handling for RFC 1918 private IPs |

## Consequences

- All SIP phones behind NAT will be reachable for inbound calls without any per-user configuration.
- FreeSWITCH will send periodic OPTIONS keepalives to NATted endpoints, generating minor additional network traffic.
- The `rfc1918.auto` ACL is built into FreeSWITCH — no custom ACL definition needed.
- Existing deployments get the fix automatically on module upgrade (`noupdate="0"` on the template data).
