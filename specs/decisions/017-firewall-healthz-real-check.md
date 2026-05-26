# ADR-017: `/firewall/healthz` reflects Odoo + ESL connectivity

**Status:** Accepted
**Date:** 2026-05-26

## Context

The firewall service ships three HTTP endpoints that look like
health information:

- `/healthz` and `/firewall/healthz` — public, both returned a
  hardcoded `{"status": "ok"}` regardless of dependency state.
- `/firewall/api/heartbeat` — authenticated (Bearer or basic auth),
  returns rich JSON intended for the dashboard.

External monitoring (Uptime Kuma, Prometheus blackbox exporter,
generic HTTP probes) needs a URL that:

1. requires no credentials (the credential store is the very thing
   that may be misconfigured),
2. returns a non-2xx HTTP status when the service is not actually
   doing its job — i.e. when Odoo or FreeSWITCH ESL is unreachable.

Neither of the existing public endpoints met point 2, and the
authenticated heartbeat carried `esl_connected: True` hardcoded with
a `# populated by ESL loop in v2` TODO from ADR-014.

The operator-facing question is "should I get paged?" — answered by
the HTTP status. The JSON body is a convenience for humans curling
the URL.

## Options

1. **Add a third route `/firewall/status`.** Symmetrical with
   `/healthz` and `/firewall/healthz`. Adds a third near-identical
   endpoint to maintain and document.
2. **Promote `/firewall/healthz` to a real readiness check; keep
   `/healthz` as the trivial liveness fallback.** Reuses the
   documented URL operators already point at. Breaking change for
   anyone reading the response body, but the HTTP status only
   regresses for environments where the service is broken anyway.
3. **Make the authenticated heartbeat public.** Smallest code
   change. Leaks internal fields (`last_sync_error`,
   `bans_count`, version string) to unauthenticated callers and
   couples monitoring to a richer JSON shape than it needs.

## Decision

**Option 2.** `/firewall/healthz` now returns:

- `200 OK` + `{"status": "ok", "odoo": true, "esl": true}` when both
  Odoo (`OdooClient.last_call_ok`) and ESL
  (`ESLClient.is_connected`) are healthy;
- `503 Service Unavailable` + `{"status": "error", "odoo": <bool>,
  "esl": <bool>}` otherwise.

`/healthz` is split off into its own handler that keeps the
unconditional `{"status": "ok"}` behaviour — Kubernetes / Traefik /
proxy liveness probes must not get 503 just because Odoo is down,
otherwise the orchestrator restarts the container in a loop while
the upstream is having a bad day. Liveness ≠ readiness.

### Why JSON + HTTP status, not plain text "OK"

Every modern monitoring agent (Uptime Kuma, blackbox exporter,
Pingdom, even `curl --fail`) decides "alert / don't alert" from the
HTTP status code. A 503 is enough. The JSON body costs nothing extra
and gives a human operator who curls the URL by hand the
breakdown they need (`{"odoo": false, "esl": true}`) without an
auth token. Plain text would force us to add response negotiation
the first time someone asked "*which* dependency failed?".

### Why 503 and not 500

503 Service Unavailable is the canonical "this server is up but
cannot service requests right now" code (RFC 9110 §15.6.4) and is
what Kubernetes readiness probes, AWS ALB target groups, and
Prometheus blackbox examples model. 500 implies an unhandled
exception — misleading when the answer "Odoo down" is itself a
correct, intentional response.

### Why not bypass via a separate router prefix

We could expose this under `/public/...` with its own router. The
existing auth middleware already has an explicit exemption list
(`/healthz`, `/firewall/healthz`); adding nothing to it is the
smallest change. A second router doubles the route table and
confuses readers who expect everything under `/firewall/*`.

### Real ESL connectivity, not a hardcoded flag

`ESLClient` now carries `is_connected: bool`, toggled inside
`_open()` (after the subscribe `+OK`), `close()`, and the
exception branch of `events()`. The `ESLClient` instance is
constructed once in `run()` and passed both to `esl_loop()` and to
`build_app()`, so the HTTP layer and the heartbeat loop read the
same source of truth. This also removes the
`# populated by ESL loop in v2` TODO from
`/firewall/api/heartbeat` and the outbound Odoo heartbeat.

## Consequences

- **Breaking change for `/firewall/healthz` callers.** The response
  body is now `{"status": "...", "odoo": <bool>, "esl": <bool>}`
  instead of `{"status": "ok"}`, and the status code can be 503.
  Searched the repo and docs: only `docs/admin/firewall.md`
  referenced this endpoint as a `curl` example. No `HEALTHCHECK` in
  the firewall Dockerfile, no docker-compose health check, no CI
  script depends on it. Existing deployments without external
  monitoring will see no behavioural change while the service is
  healthy.
- **`/healthz` remains stable** for liveness probes that must never
  flap on upstream failure.
- **Firewall image bumped to `oduist/freeswitch-firewall:1.1.1`.**
  Rollout order: push image → restart service container. No Odoo
  changes are required — the service-side endpoint shape is the
  only thing that changed.
- **Operator guidance updated** in `docs/admin/firewall.md`
  Troubleshooting: external monitoring should point at
  `/firewall/healthz`; `/healthz` is for process-only checks;
  `/firewall/api/heartbeat` stays as the dashboard / debugging
  endpoint behind auth.

## References

- ADR-014 — original firewall service design (this ADR completes
  the v2 ESL-state TODO it called out).
- ADR-015 — shared-bearer auth model (unchanged here; `/healthz`
  and `/firewall/healthz` were already on the middleware
  exemption list).
- `connect_freeswitch/deploy/firewall/src/connect_firewall_service/http_server.py` — the new handlers.
- `connect_freeswitch/deploy/firewall/src/connect_firewall_service/esl.py` — the `is_connected` flag.
- RFC 9110 §15.6.4 — semantics of HTTP 503 Service Unavailable.
