# ADR-003: FreeSWITCH Domain & Single Profile

**Date:** 2026-03-17
**Status:** Accepted

## Problem
1. Directory XML used hardcoded IP fallback `80.246.208.201` from a specific deployment.
2. `endpoint.domain` was a per-endpoint field, but domain should be global — all endpoints share the same FreeSWITCH instance.
3. Static `sip_profiles/internal.xml` was dead code — the sofia profile is served dynamically from Odoo via xml_curl.
4. Sofia profile had no `force-register-domain` / `force-realm`, so `Domain Name` showed as `N/A`.

## Options Considered
1. **Keep per-endpoint domain** — Allows multi-FS setups. But we have one FS instance, and the field was confusing (usually left empty, falling back to hardcoded IP).
2. **Global `freeswitch_domain` setting (chosen)** — Single source of truth. Used in directory XML, sofia config, and bridge URIs.
3. **Read domain from FS request params only** — No Odoo-side config needed, but FS sends its IP as domain which isn't useful for SIP routing.

## Decision
Option 2 — Global `freeswitch_domain` setting in `connect.settings`. Removed `endpoint.domain` field, deleted dead static `internal.xml` profile. Added `force-register-domain`, `force-realm`, `force-register-db-domain` to the dynamic sofia config so registrations are tied to the configured domain.

A single `external` profile handles all use cases: gateway trunks (auth or IP ACL), SIP user registration, and Verto. Context separation (`public` for inbound, `default` for registered users) provides the routing boundary.
