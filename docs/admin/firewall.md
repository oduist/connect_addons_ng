# Firewall Service — SIP brute-force protection

The `connect_freeswitch` module ships with an out-of-process firewall
service that pairs with FreeSWITCH and blocks SIP brute-force attempts
at the kernel level. It is **disabled by default** and turned on with a
single toggle once you've added the supporting container.

## What it does

Every SIP REGISTER / INVITE that FreeSWITCH sees produces an event on
the ESL bus. The firewall service listens, classifies the event, and
moves the source IP between six `ipset` tables that an `iptables` chain
in front of the SIP ports consults at line rate:

| ipset | TTL | What happens to traffic from listed IPs |
|---|---|---|
| `connect_fw_whitelist` | permanent | always ACCEPT |
| `connect_fw_blacklist` | permanent | always DROP (admin-managed) |
| `connect_fw_authenticated` | 7 d (sliding) | ACCEPT — IP has registered successfully |
| `connect_fw_banned` | 24 h | DROP — auto-ban after a failed authentication |
| `connect_fw_expire_short` | 30 s | ACCEPT — challenge response window after a SIP 401 |
| `connect_fw_expire_long` | 24 h | DROP — default-deny after a challenge is sent but not answered |

Both address families are covered: each table above is the IPv4
(`family inet`) set, and a `6`-suffixed twin (`connect_fw_whitelist6`,
`connect_fw_banned6`, …) holds the IPv6 entries, consulted by an
identical `connect_fw_voip` chain installed via `ip6tables`. Whitelist
and blacklist entries in Odoo accept both families and are routed to
the right set automatically; on hosts without IPv6 (`ipv6.disable=1`)
the service logs an error for the v6 family and keeps protecting IPv4.

In addition, an `iptables -m string` filter at the bottom of the chain
DROPs known SIP-scanner User-Agents (`friendly-scanner`, `sipvicious`,
`sipcli`, `VaxSIPUserAgent`, `sundayddr`, `sipsak`, `sip-scan`) before
they even reach FreeSWITCH.

## How a session flows

1. Phone sends REGISTER. FreeSWITCH issues a 401 challenge → IP lands in
   `expire_short` (30 s pass) **and** `expire_long` (24 h default-deny).
2. Phone re-sends REGISTER with credentials.
   - **Correct** → `sofia::register` event → IP moves to
     `authenticated` (7 days, sliding). All further packets ACCEPT.
   - **Wrong** → `sofia::register_attempt` with `auth-result=FORBIDDEN`
     and/or `sofia::register_failure` → IP moves to `banned` (24 h).
     Subsequent packets DROP.
3. An INVITE without an established session emits
   `sofia::wrong_call_state` → treated as toll-fraud, IP banned.

A whitelisted IP / CIDR short-circuits the whole pipeline.

## Components

```
┌──────────────┐     POST /firewall/sync (Bearer)      ┌──────────────────┐
│     Odoo     │ ─────────────────────────────────────▶│ firewall service │
│ (connect_fw) │ ◀── HTTP /freeswitch/firewall/api/* ──│ (oduist/         │
│              │     (Bearer; fetch/report)            │  freeswitch-     │
│ - whitelist  │                                       │  firewall)       │
│ - blacklist  │            ESL events                 │                  │
│ - events log │            ◀────────────              │ - ipset / iptables
│ - settings   │                                       │ - HTTP / SSE
│ - agent st.  │                                       │   dashboard
└──────────────┘                                       └─────────┬────────┘
                                                                 │ ESL :8021
                                                                 ▼
                                                          ┌──────────────┐
                                                          │  FreeSWITCH  │
                                                          └──────────────┘
```

* **Odoo** owns the configuration, the static whitelist/blacklist, the
  event audit log and the agent status singleton. It exposes a small
  HTTP control plane under `/freeswitch/firewall/api/*` that the
  service polls (`config`, `whitelist`, `blacklist`) and posts to
  (`heartbeat`, `event`, `applied`).
* **firewall service** is a small async Python container; it talks to
  FreeSWITCH via `mod_event_socket` (ESL), to Odoo over plain HTTP
  authenticated with a shared Bearer token, and manipulates `ipset` /
  `iptables` on the host kernel. It also serves a Lit-based dashboard
  at `/firewall/`.

Both directions use the **same** shared secret
(`connect.settings.firewall_service_token` in Odoo, `AGENT_TOKEN` env
var on the service). There is no dedicated Odoo user for the service.

The data plane (`ipset` + `iptables`) lives in the host kernel and is
**not** affected by restarts of either container.

## Installing the firewall service

The service container must:

* run with **`network_mode: host`** (it needs to talk to ESL on
  `127.0.0.1:8021` and have `iptables` see the real outside traffic);
* hold the **`NET_ADMIN`** capability so `ipset` / `iptables` syscalls
  succeed against the host kernel.

### Required environment variables

| Variable | Purpose |
|---|---|
| `ODOO_URL` | base URL of the Odoo instance (e.g. `https://pbx.example.com`). The service appends `/freeswitch/firewall/api/*` paths to it. |
| `AGENT_TOKEN` | shared Bearer token. Must match **Firewall Service Token** in Odoo settings. Used in both directions (this service → Odoo and Odoo → `/firewall/sync` on this service). The service refuses to start without it. |
| `FS_ESL_HOST` | usually `127.0.0.1` |
| `FS_ESL_PORT` | usually `8021` |
| `FS_ESL_PASSWORD` | password of FreeSWITCH `mod_event_socket`. The shipped FS image bakes in `ConnectNGESLPassword`; set `FS_ESL_PASSWORD` on both containers if you want a different value. |
| `HTTP_BIND_HOST`, `HTTP_BIND_PORT` | where the service listens (default `0.0.0.0:8081`; set `HTTP_BIND_HOST=::` if the dashboard itself must be reachable over IPv6) |
| `DASHBOARD_USER`, `DASHBOARD_PASSWORD` | basic-auth credentials for the dashboard / JSON API |

Optionally:

| Variable | Effect |
|---|---|
| `LOG_LEVEL` | `INFO` (default) or `DEBUG` |
| `CONFIG_CACHE_PATH` | local JSON cache (default `/var/lib/connect-firewall/config.json`) |

### Docker Compose example

```yaml
firewall:
  image: oduist/freeswitch-firewall:2.1.0
  network_mode: host
  cap_add: [NET_ADMIN]
  environment:
    ODOO_URL: https://pbx.example.com
    AGENT_TOKEN: <copy from Firewall Service Token in Odoo settings>
    FS_ESL_HOST: 127.0.0.1
    FS_ESL_PASSWORD: ConnectNGESLPassword
    DASHBOARD_USER: admin
    DASHBOARD_PASSWORD: <pick a strong password>
  volumes:
    - firewall-cache:/var/lib/connect-firewall
```

A ready preset for `oduflow` lives at
`connect_freeswitch/deploy/firewall/oduflow-preset.yaml`.

## Setting up in Odoo

1. Install or upgrade `connect_freeswitch` — `post_init_hook` (or the
   per-version migration on upgrade) generates an initial **Firewall
   Service Token** and creates the agent singleton.
2. Open **Connect → FreeSWITCH → Configuration → Settings**, page **Firewall**, as an admin:
   * Toggle **Firewall Enabled** on.
   * Set **Firewall Service URL** to where Traefik (or whichever
     reverse-proxy you use) reaches the service container.
   * **Firewall Service Token**: either keep the auto-generated value
     or paste your own (≥24 chars, `[A-Za-z0-9_-]` only). Copy the
     value into the `AGENT_TOKEN` env var of the firewall service
     container **before saving**, because the field gets masked back
     to `****` immediately after. Restart the service container so it
     picks up the new token.
   * Adjust port lists and timeouts if you need to deviate from the
     defaults.
3. Connect → FreeSWITCH → Firewall → **Whitelist**: add your trunk providers,
   office NAT exits, anything you don't want auto-banned. Save —
   `connect.firewall.agent._trigger_sync()` will POST to
   `/firewall/sync` immediately.
4. Connect → FreeSWITCH → Firewall → **Agent Status**: should show the agent
   as *online* within one heartbeat interval (default 60 s).

## Daily operations

* **Active auto-bans** — they live only in the kernel. View them on
  the service's dashboard:
  `https://<your-host>/firewall/` (basic-auth with `DASHBOARD_USER` /
  `DASHBOARD_PASSWORD`). Each row has an Unban button.
* **From Odoo** — open `Connect → FreeSWITCH → Firewall → Events`. Every row
  with **Event Type = Automatic Ban** gets a small unlock-icon
  button. Clicking it calls back into the service to remove the IP
  from `connect_fw_banned` and writes a `manual_unban_applied`
  audit record. The button hides itself as soon as the IP is no
  longer banned.
* **Permanent block** — `Connect → FreeSWITCH → Firewall → Blacklist`, add an
  IP or CIDR. Useful for blocking entire VPS-provider subnets.

## Settings reference

| Setting | Default | Effect |
|---|---|---|
| Firewall Enabled | False | Master switch. When off, the service still runs but reports `firewall_enabled=False`. |
| Firewall Service URL | `http://host.docker.internal:8081` | Odoo posts `/firewall/sync` here. |
| Firewall Service Token | *generated* | Shared Bearer secret. ≥24 chars, `[A-Za-z0-9_-]` only. The service uses the same value for both directions; restart the container after changing it. |
| Heartbeat Interval | 60 s | How often the service pings Odoo. |
| Event Retention | 30 days | How long the audit log is kept; the daily cron prunes older. |
| Firewall TCP/UDP Ports | `5060,5061,5080,5081` | Where the chain hooks in. Must match the ports `sofia` actually listens on. |
| Auto-ban TTL | 86400 s (24 h) | How long an auto-ban stays in `connect_fw_banned`. |
| Trust TTL | 604800 s (7 d) | How long a successful registration buys trust. |
| Challenge Window | 30 s | `expire_short` lifetime. |
| Default-Deny TTL | 86400 s (24 h) | `expire_long` lifetime if the challenge is never answered. |

## Troubleshooting

```bash
# 1a. Process-level liveness (no auth, always 200 while the service is up).
#     Wire this to Kubernetes / Traefik / Docker liveness probes — it must
#     not flap when Odoo is down, otherwise the orchestrator restarts the
#     container in a loop while the upstream recovers.
curl -sk https://<host>/healthz

# 1b. Dependency-aware readiness check (no auth, the URL to point external
#     monitoring at — Uptime Kuma, Prometheus blackbox exporter, etc.).
#     Returns 200 + {"status":"ok","odoo":true,"esl":true} when both Odoo
#     and FreeSWITCH ESL are reachable; 503 + {"status":"error","odoo":...,
#     "esl":...} otherwise.
curl -sk -i https://<host>/firewall/healthz

# 1c. Rich JSON for the dashboard (auth required — Bearer token or basic).
curl -sk -u admin:<pw> https://<host>/firewall/api/heartbeat | jq

# 2. Is ESL really connected?
docker logs <firewall-container> | grep -E "ESL connected|Reconciler|AUTO-BAN"

# 3. Look at the actual kernel state (the "6"-suffixed sets and
#    ip6tables are the IPv6 side).
ipset list connect_fw_banned
ipset list connect_fw_banned6
ipset list connect_fw_authenticated
iptables -L connect_fw_voip -v -n
ip6tables -L connect_fw_voip -v -n

# 4. Verify the chain is hooked into INPUT for both families.
iptables -L INPUT -v -n | grep connect_fw_voip
ip6tables -L INPUT -v -n | grep connect_fw_voip
```

If the agent stays *offline* in Odoo:

* check that `AGENT_TOKEN` in the service env matches **Firewall
  Service Token** in Odoo settings — the easiest mistake is rotating
  the token in Odoo but not redeploying the container;
* check that `/freeswitch/firewall/api/heartbeat` on Odoo is reachable
  from inside the firewall container (curl with the Bearer header
  should return `{"ok":true}`);
* check that `/firewall/sync` is reachable from inside the Odoo
  container — Odoo sends notifications to this URL, not the service
  to Odoo.

If you see events arrive in Odoo but no auto-bans land in `ipset`:

* the container is running without `NET_ADMIN` — `ipset add` returns
  `Operation not permitted`, visible in the service logs;
* the kernel does not have the `ip_set` / `xt_set` modules
  available — typical on hardened/minimal hosts. `modprobe ip_set`
  on the host fixes it. The IPv6 side additionally needs `ip6_tables` /
  `ip6table_filter`; on hosts booted with `ipv6.disable=1` the service
  logs an error for the v6 family and continues IPv4-only — that is the
  expected degradation, not a fault.

## Architecture-level reference

See `specs/decisions/014-freeswitch-firewall-service.md` for the
design decisions behind this stack (six-table ipset model, direct
HTTP control plane, hardcoded UA blacklist, single-instance) and
`specs/decisions/037-firewall-ipv6-support.md` for how IPv6 was
layered in (parallel `inet6` sets + `ip6tables` chain).
