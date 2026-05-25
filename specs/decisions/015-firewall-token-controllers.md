# ADR-015: Firewall service uses shared-bearer HTTP controllers (drop the portal user)

**Status:** Accepted
**Date:** 2026-05-25

## Context

ADR-014 shipped the firewall service with two parallel auth schemes:

- **Service → Odoo**: log in as a dedicated portal user
  (`freeswitch_agent`) with a generated password, then call
  `connect.firewall.agent.<method>(...)` via JSON-RPC (`/jsonrpc` →
  `execute_kw`).
- **Odoo → service**: POST `/firewall/sync` and DELETE
  `/firewall/api/bans/<ip>` with `Authorization: Bearer
  <firewall_service_token>` (the same shared secret).

A bootstrap fallback also let the service pull `AGENT_TOKEN` out of
`fetch_config()` on first successful login.

In practice this turned out to be more machinery than the use case
deserves:

- one extra Odoo user, one extra group, five `ir.model.access` rules,
  a `setup_firewall()` helper that has to strip Role/User and add
  Role/Portal to dodge Odoo 19's exclusive-role validator;
- an extra secret (`freeswitch_agent_password`) that the admin can
  never read back (the field is masked immediately after save), so
  rotating it always means a service downtime window;
- a tolerant `_first_dict(*values)` shim on every inbound method to
  cope with how different RPC clients serialise positional
  arguments;
- two completely different auth paths for the same shared trust
  boundary, which is harder to reason about than one.

We already had the right primitive for both directions — a shared
`firewall_service_token` used for the Odoo → service half. The
portal user is the only reason it wasn't used the other way around.

## Options

1. **Keep the portal user; do nothing.** Status quo. Burden documented
   above.
2. **Symmetric shared bearer over dedicated HTTP controllers.** Add a
   `connect_freeswitch.controllers.firewall_api` with six routes
   (`config`, `whitelist`, `blacklist`, `heartbeat`, `event`,
   `applied`) under `/freeswitch/firewall/api/*`. Each route
   validates `Authorization: Bearer <firewall_service_token>` with
   `secrets.compare_digest` and then `sudo()`s. Drop the user,
   group, ACLs, password field, and the `aio_odoorpc` dependency.
3. **mTLS between Odoo and the service.** Stronger crypto story, but
   requires CA management, certificate distribution, and would not
   compose well with the Traefik reverse-proxy fronting both sides
   in the current deployment shape. Overkill for a single shared
   secret that already exists.
4. **OAuth2 client-credentials.** Standards-friendly, but adds an
   authorisation server (or in-process token issuer) and a refresh
   loop for what is fundamentally a one-trust-boundary case.

## Decision

**Option 2.** Drop the portal user; both directions authenticate with
the same `firewall_service_token` carried as `Authorization: Bearer
<token>`. The service-side endpoints stay where they were; the new
Odoo-side endpoints live under `/freeswitch/firewall/api/*`.

### Route shape

| Route | Method | Body | Returns |
|---|---|---|---|
| `/freeswitch/firewall/api/config` | `GET` | — | dict of `firewall_*` settings |
| `/freeswitch/firewall/api/whitelist` | `GET` | — | list of `{id, name, ip_or_cidr, note}` |
| `/freeswitch/firewall/api/blacklist` | `GET` | — | list of `{id, name, ip_or_cidr, note}` |
| `/freeswitch/firewall/api/heartbeat` | `POST` | `{version, esl_connected, bans_count, authenticated_count, uptime_seconds}` | `{"ok": true}` |
| `/freeswitch/firewall/api/event` | `POST` | `{event_type, ip, user_agent, account_id, service, details, ts}` | `{"ok": true, "id": <int>}` |
| `/freeswitch/firewall/api/applied` | `POST` | `{ip, action, status, message}` | `{"ok": true}` |

All routes use `@http.route(type='http', auth='none', csrf=False)`.
Bare JSON in / bare JSON out — no JSON-RPC envelope. 401 on missing
or wrong Bearer, 400 on malformed JSON, 200 on success.

### What gets removed

- `connect_freeswitch.user_freeswitch_agent` + its partner record;
- `connect_freeswitch.group_freeswitch_agent`;
- the five `access_firewall_*_agent` and `access_connect_settings_freeswitch_agent` rules in `security/access_rules.xml`;
- the `freeswitch_agent_password` / `display_freeswitch_agent_password` fields on `connect.settings` and the password-validation/propagation branches in `_validate_firewall_secret` and `write()`;
- the `action_generate_firewall_token` UI button (the token is no longer auto-bootstrapped by the service, so a generator that doesn't reveal the new value would just break the service);
- `_first_dict(*values)` and the `*args, **kwargs` tail on every inbound model method;
- the `aio-odoorpc` dependency on the service side;
- the `agent_token`-from-`fetch_config()` fallback in the service reconciler.

### What stays

- `firewall_service_token` and the masked `display_firewall_service_token` field, validated as before (≥24 chars, `[A-Za-z0-9_-]`).
- The `connect.firewall.agent` model and all its public methods (signatures simplified — they're now called from a controller, not via XML-RPC).
- All six ipset tables, ESL handler logic, dashboard, sync semantics — untouched.
- `firewall_service_url` for the Odoo → service direction.

### Bootstrap & failure modes

The service requires `AGENT_TOKEN` in env. If unset, pydantic raises a
`ValidationError` at startup. This is a deliberate trade-off versus
the old fallback: a hard failure at boot is easier to diagnose than a
service that silently rejects every `/firewall/sync` until first
login.

The token in `connect.settings` is still generated on install /
upgrade by `setup_firewall(env)` so a fresh installation has a sane
default; the admin copies it into the service env before saving the
form.

### Why not `with_user(user_connect_webhook)` on the controllers

We considered routing the `sudo()`ed calls through
`request.env[...].with_user(request.env.ref('connect.user_connect_webhook').id)`
to mirror the FreeSWITCH CDR webhook controller's pattern. We didn't
because (a) it would force us to keep `ir.model.access` rows for the
webhook group on every firewall model, which is exactly the
machinery we just deleted, and (b) the token is the only real trust
boundary — once it matches, `sudo()` is the cleanest expression of
"the service is authorised to do this". The webhook user remains the
right pattern for *third-party* webhooks (Twilio, FreeSWITCH CDR)
where the trust boundary is asymmetric.

## Consequences

- One shared secret to manage; one auth path to audit. Same secret
  rotates both directions; restart the service container after
  rotating it in Odoo.
- The service container fails fast on missing `AGENT_TOKEN` instead of
  silently degrading. Operators see the problem in the first
  `docker logs` page.
- The Docker image is bumped to `oduist/freeswitch-firewall:1.1.0`.
  Rollouts must order: push image → upgrade Odoo module → restart
  service container. An older image hitting the new Odoo (where the
  portal user is gone) will fail to log in.
- Migration `19.0.1.8.17/post-migrate.py` is the only mechanism that
  removes the existing user/partner/group/password from already-installed
  databases — the user record was loaded under `noupdate="1"`, so
  removing the XML alone would not unlink it. Forgetting the manifest
  version bump (which is what associates the migration folder with
  the upgrade pass) would leave the user orphaned. Verified by a DB
  query in the verification plan.
- 18.0 backport is straightforward but tracked as a separate change
  (the 18.0 branch carries its own `19.0.1.8.x` → `18.0.1.8.x`
  alignment per `CLAUDE.md`).

## References

- ADR-014 — original firewall service design (six-table model still in force; portal-user auth pieces marked superseded by this ADR).
- `connect_freeswitch/controllers/firewall_api.py` — the new controllers.
- `connect_freeswitch/migrations/19.0.1.8.17/post-migrate.py` — the cleanup.
- `connect_twilio/controllers/twilio_webhooks.py` — convention this controller follows for header-based auth (`secrets.compare_digest`, early-return on bad signature).
