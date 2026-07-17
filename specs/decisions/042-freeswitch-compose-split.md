# ADR-042: Split FreeSWITCH compose files and include the firewall service

**Status:** Accepted
**Date:** 2026-07-13

## Context

`connect_freeswitch/deploy/docker-compose.yml` had drifted into a mixed
shape: it bundled Odoo and Postgres like a local development stack, but
also carried production-facing Traefik and FreeSWITCH configuration. It
still used `safarov/freeswitch:latest`, while the deploy image policy and
operator docs expect the curated `oduist/freeswitch` image. It also did
not start the paired SIP firewall service even though the module, specs
and admin docs describe the firewall as part of the FreeSWITCH host.

The most common operational workflow is a dedicated FreeSWITCH host
paired with an Odoo deployment running elsewhere. Local all-in-one use is
still useful, but it should not be the default file copied to customer
hosts.

## Decision

Make `deploy/docker-compose.yml` the production FreeSWITCH host stack:
Traefik, `oduist/freeswitch:2.1.0` and
`oduist/freeswitch-firewall:2.1.0`, without Odoo or Postgres.

Add `deploy/docker-compose.full.yml` as the standalone all-in-one stack
for local development and smoke testing. It keeps Odoo 19 and Postgres
from the old file and adds the same Traefik, FreeSWITCH and firewall
services used by production.

Traefik now runs on the host network and proxies to loopback-only
control-plane listeners:

- `/RPC2` → `127.0.0.1:8080` for FreeSWITCH XML-RPC;
- `/firewall` → `127.0.0.1:8081` for the firewall service.

The firewall container runs with `network_mode: host` and `NET_ADMIN` so
it can manage host `ipset` / `iptables` / `ip6tables` state and connect
to FreeSWITCH ESL on `127.0.0.1:8021`. The compose files require
installation-specific secrets via `.env` instead of committing usable
defaults.

## Consequences

- Copying `connect_freeswitch/deploy/` to a customer host now gives the
  expected production layout by default.
- The firewall service starts with FreeSWITCH and is reachable publicly
  only through Traefik's `/firewall` route.
- Local all-in-one use remains available through
  `docker compose -f docker-compose.full.yml up -d`.
- No module version bump and no image rebuild are required because only
  compose templates and documentation changed.

## References

- ADR-014 — FreeSWITCH firewall service.
- ADR-030 — TLS for FreeSWITCH XML-RPC via Traefik.
- ADR-037 — IPv6 support in the FreeSWITCH firewall service.
