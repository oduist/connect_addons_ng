# ADR-014: FreeSWITCH firewall service (SIP brute-force protection)

**Status:** Accepted
**Date:** 2026-05-20

## Context

`connect_freeswitch` exposes SIP/TCP/UDP to the public network. Without protection, hosts get hit within minutes by SIP scanners (`friendly-scanner`, `sipvicious`, `sipcli` and similar), password-guessing bots, and toll-fraud INVITE floods. We need:

- automatic blocking of IPs that fail authentication;
- a static admin-managed whitelist (offices, VPN exits, SIP-trunk providers);
- a static admin-managed blacklist (permanent manual bans);
- a history of security events visible in Odoo;
- a way to manage all of the above from the Odoo UI without giving Odoo direct access to host firewall rules.

`connect_twilio` does not have the same problem because Twilio traffic flows through webhooks where authenticity is verified by signature; firewall protection is only required for the SIP-facing FreeSWITCH path.

We already have a working reference implementation in our Asterisk product (see `.context/attachments/UPq7uy/pasted_text_2026-05-20_15-30-58.txt`) that has run in production for years. It pairs an out-of-process agent with Odoo and uses `ipset`/`iptables` for the actual blocking.

## Options

1. **fail2ban** — parse FreeSWITCH logs, ban via iptables/ipset. Battle-tested, but: log-driven (slower than event-driven), no Odoo integration without writing custom actions, no built-in dynamic trust, harder to surface state in our UI.
2. **FreeSWITCH `mod_security2`** — built-in. Provides basic protection at the SIP layer, but limited control over ipset/iptables, no UI integration, requires reloads.
3. **Pure ACL in `sofia` + `acl.conf.xml`** — static, requires `sofia reload`, no dynamic bans at all.
4. **Custom out-of-process service** with ESL events + ipset + Odoo control plane. Mirrors the Asterisk-side architecture we already operate.

## Decision

Build a **dedicated firewall service** that runs alongside FreeSWITCH and is managed from Odoo.

### Service shape

- One Docker container, host network, `cap_add: NET_ADMIN`.
- Connects to FreeSWITCH via `mod_event_socket` (ESL).
- Connects to Odoo as a portal user (no enterprise-license consumption).
- Exposes HTTP on `127.0.0.1:8081`, fronted by the same Traefik that already sits in front of Odoo, under `/firewall/*` with basic auth.
- All state in the kernel (`ipset`/`iptables`); the service itself is stateless beyond a JSON config cache.

### Six ipset tables with challenge window

Inherited from the Asterisk-side reference, because it cleanly handles the "ban on first failure without breaking legitimate clients" requirement:

| Table | Type | TTL | Source |
|---|---|---|---|
| `connect_fw_whitelist` | `hash:net` | permanent | Odoo |
| `connect_fw_blacklist` | `hash:net` | permanent | Odoo (manual permanent bans) |
| `connect_fw_authenticated` | `hash:ip` | 7 d sliding | ESL: successful REGISTER |
| `connect_fw_banned` | `hash:ip` | 24 h | ESL: failed auth |
| `connect_fw_expire_short` | `hash:ip` | 30 s | ESL: challenge sent |
| `connect_fw_expire_long` | `hash:ip` | 24 h | ESL: challenge sent |

iptables chain `connect_fw_voip` evaluates them in order: whitelist → blacklist → authenticated → banned → expire_short (ACCEPT 30 s) → expire_long (DROP 24 h) → UA string match (`-m string ... -j DROP`) → default ACCEPT.

The `expire_short`/`expire_long` pair is the key: a new IP that has just been issued a `401` gets 30 s to respond correctly. If the response succeeds → `authenticated` (7 days). If it fails → `banned` (24 h). If the IP never responds → `expire_long` keeps it blocked for 24 h. Legitimate SIP phones always respond correctly to their first challenge and are immediately trusted, so the "ban on first failure" policy does not produce false positives for them. CGNAT-shared IPs benefit from the same trust window: a single successful registration from anyone in the NAT pool buys 7 days of trust for the whole IP.

### Transport: direct HTTP, not FreeSWITCH events

Initial design considered using FS `CUSTOM` events as a control-plane channel from Odoo to the service. We rejected that in favour of plain HTTP because:

- the service already has a Traefik-fronted HTTP surface for the dashboard, so adding `/firewall/sync` is free;
- HTTP is debuggable with `curl`;
- HTTP has well-defined error codes and timeouts;
- it removes a dependency on FreeSWITCH liveness for the control plane.

Communication:
- Odoo → service: `POST /firewall/sync` (signal only, no payload), triggered by a `postcommit` hook on any CRUD on firewall models and by a `ir.cron` reconcile every 5 minutes.
- Service → Odoo: XML-RPC under the portal user — `fetch_config`, `fetch_whitelist`, `fetch_blacklist`, `report_event`, `report_applied`, `report_heartbeat`.

### Declarative sync semantics

`POST /firewall/sync` is a notification — "state changed, refetch". The service pulls the desired state from Odoo and diffs it against the live `ipset` contents. This makes the same code path serve both event-driven and periodic reconciliation, and gives idempotency for free.

### No attempt-count thresholds, no escalation

Detection is event-shape-driven, not count-driven: one `register_failure` → one `ipset add banned`, all auto-bans live for exactly 24 h. There is no "5 failures in 60 s" counter, no escalation to 7-d / 30-d bans, no permanent auto-bans. Permanent blocking is exclusively the admin's prerogative through `connect.firewall.blacklist` in Odoo. Rationale: the challenge-window mechanism already gives legitimate clients all the room they need (one correct response and they are trusted for a week), so an extra "you may fail N times" budget is both unnecessary and a source of false negatives against patient attackers.

### UA blacklist hardcoded in the service

The list of malicious User-Agent substrings (`friendly-scanner`, `sipvicious`, `sipcli`, `VaxSIPUserAgent`, `sundayddr`, `sipsak`, `sip-scan`) is a constant in the service code, applied at the kernel layer via `iptables -m string`. Rationale: this list changes very rarely, kernel-level matching is faster than parsing UA in userspace, and adding entries via PR + image bump is simpler than maintaining yet another Odoo model. If the list ever needs to be data-driven, that is a v2 concern.

### One portal user, used by the firewall service and future FS→Odoo integrations

`connect_freeswitch/data/res_users.xml` defines `user_freeswitch_agent`, a portal user (`share=True`, member of `base.group_portal`). It does not consume an enterprise seat. The firewall service authenticates as this user; future FS-side automation (provisioning, phone sync, etc.) will reuse the same identity. Per-resource access is granted point-by-point through `ir.model.access`:

- whitelist/blacklist: read only;
- events: read + create (cannot edit history);
- agent singleton: read + write (for heartbeat).

The service has no permission to create or modify whitelist/blacklist records — those are admin-only via the UI. This keeps the trust boundary clear: the service is allowed to *report* what happened and *receive* commands, but it cannot grant or revoke trust on its own.

### IPv4 only, single instance, in-memory state

- **IPv4 only.** No public IPv6 in the current installation; if added later, a parallel `ip6tables` chain and `family inet6` ipsets can be layered in without changing the model.
- **Single instance.** One FreeSWITCH = one firewall service. No `agent_id` keys in the data model.
- **No SQLite.** Bans live in the kernel ipset (which survives container restart — only host reboot wipes them). The dashboard event stream is an in-memory ring buffer (lost on service restart; full history is in Odoo). Pending outbound events to Odoo are an in-memory queue with retry (some loss possible if Odoo is unreachable while the service restarts; the kernel-level bans are unaffected). If this proves insufficient in production, a SQLite outbox is a v2 addition.

### Dashboard via Lit + ESM CDN

The service ships a small operational dashboard at `/firewall/` for live state (active bans with TTL countdown, event stream, attempts-per-minute sparkline, top-10 IPs, heartbeat panel). Implementation:

- FastAPI + Jinja2 renders a single HTML shell;
- frontend is a handful of Lit custom elements imported from `https://esm.sh/lit` — no bundler, no `node_modules`, no build step;
- live updates over SSE (`text/event-stream`).

Chosen Lit because each widget has its own reactive local state (a TTL countdown ticks once per second per row), which is the native pattern for `LitElement`. Alpine.js or vanilla JS would also work; the choice can be revisited if frontend complexity grows, but for the current widget set Lit is the cleanest fit and stays a five-kilobyte dependency.

### Everything lives in `connect_freeswitch`

We considered creating a separate `connect_firewall` Odoo module that depends on `connect_freeswitch`. We rejected that because the feature is meaningful only when FreeSWITCH is present; an extra module boundary buys nothing and adds a dependency edge to maintain. The whole feature can be disabled with a single `firewall_enabled = False` setting in `connect.settings`.

## Consequences

- Brute-force protection becomes a first-class feature of the SIP integration; default-on after configuration (token + dashboard credentials) and admin-controlled.
- All security events flow into Odoo and are visible alongside calls, recordings, and other telephony artefacts. Compliance/audit story improves.
- The kernel (`ipset` + `iptables`) is the actual data plane; if the service or Odoo are down, existing bans and trust still apply. The control plane degrades gracefully — auto-ban detection keeps working without Odoo (events queue in memory and flush when Odoo comes back).
- One new Docker image to maintain (`oduist/connect-firewall`), versioned independently from the Odoo module.
- A new portal user (`freeswitch_agent`) becomes the canonical identity for FreeSWITCH-side automation — future provisioning/sync work reuses it instead of inventing more service accounts.
- The Asterisk-derived 6-table scheme is now duplicated in two codebases (Asterisk agent + FreeSWITCH service). They will diverge over time; that is acceptable because the two are independent products.
- IPv6, multi-instance, escalation, and a data-driven UA blacklist are explicit non-goals for v1. Each can be added later without re-architecting.

## Open questions to resolve during implementation

1. **Exact FreeSWITCH ESL event names** for the Asterisk equivalents of `SuccessfulAuth` / `ChallengeSent` / `InvalidPassword`. The best candidates are `sofia::register`, `sofia::register_attempt`, and `sofia::register_failure` with varying `failure-status`/`auth-result` headers. To be confirmed by subscribing to `event plain ALL` on a test FreeSWITCH and replaying valid/invalid REGISTER scenarios. Findings to be recorded as comments in the ESL handler module.
2. **Whitelist seeding for SIP-trunk providers** (Twilio Elastic SIP, Voxbeam, etc.) is left as an admin task documented in `docs/admin/firewall.md`. No code-side presets in v1 — keeps the project independent of any particular provider.

## References

- `.context/firewall_service_plan.md` — implementation plan derived from this ADR.
- `.context/attachments/UPq7uy/pasted_text_2026-05-20_15-30-58.txt` — Asterisk-side reference agent (boot installation of the 6-table scheme).
- ADR-004 `freeswitch-xml-rpc.md` — Odoo↔FreeSWITCH XML-RPC channel used by other features.
- ADR-008 `freeswitch-gateway-acl.md` — static ACL precedent at the SIP layer.
