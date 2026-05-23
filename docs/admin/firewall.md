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
┌──────────────┐     postcommit POST /firewall/sync    ┌──────────────────┐
│     Odoo     │ ─────────────────────────────────────▶│ firewall service │
│ (connect_fw) │ ◀──── XML-RPC report_event/heartbeat ─│ (oduist/         │
│              │                                       │  freeswitch-     │
│ - whitelist  │            ESL events                 │  firewall)       │
│ - blacklist  │            ◀────────────              │                  │
│ - events log │                                       │ - ipset / iptables
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
  event audit log and the agent status singleton.
* **firewall service** is a small async Python container; it talks to
  FreeSWITCH via `mod_event_socket` (ESL), to Odoo via XML-RPC, and
  manipulates `ipset` / `iptables` on the host kernel. It also serves
  a Lit-based dashboard at `/firewall/`.

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
| `ODOO_URL` | base URL of the Odoo instance (e.g. `https://pbx.example.com`) |
| `ODOO_DB` | database name |
| `ODOO_USER` | always `freeswitch_agent` (created by the module's post_init_hook) |
| `ODOO_PASSWORD` | the value the admin sets in **Configuration → General Settings → Firewall → FreeSWITCH Agent Password** |
| `FS_ESL_HOST` | usually `127.0.0.1` |
| `FS_ESL_PORT` | usually `8021` |
| `FS_ESL_PASSWORD` | password of FreeSWITCH `mod_event_socket`. The shipped FS image bakes in `ConnectNGESLPassword`; set `FS_ESL_PASSWORD` on both containers if you want a different value. |
| `HTTP_BIND_HOST`, `HTTP_BIND_PORT` | where the service listens (default `0.0.0.0:8081`) |
| `DASHBOARD_USER`, `DASHBOARD_PASSWORD` | basic-auth credentials for the dashboard / JSON API |

Optionally:

| Variable | Effect |
|---|---|
| `AGENT_TOKEN` | If set, used as the shared Bearer token for inbound `/firewall/sync` requests. If left empty, the service fetches the current token from Odoo on first login. |
| `LOG_LEVEL` | `INFO` (default) or `DEBUG` |
| `CONFIG_CACHE_PATH` | local JSON cache (default `/var/lib/connect-firewall/config.json`) |

### Docker Compose example

```yaml
firewall:
  image: oduist/freeswitch-firewall:1.0.9
  network_mode: host
  cap_add: [NET_ADMIN]
  environment:
    ODOO_URL: https://pbx.example.com
    ODOO_DB: production
    ODOO_USER: freeswitch_agent
    ODOO_PASSWORD: <copy from Odoo settings>
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
   per-version migration on upgrade) creates the portal user
   `freeswitch_agent`, generates an initial token and password, and
   creates the agent singleton.
2. Open **Configuration → General Settings → Firewall** as an admin:
   * Toggle **Firewall Enabled** on.
   * Set **Firewall Service URL** to where Traefik (or whichever
     reverse-proxy you use) reaches the service container.
   * Click the **🔄** next to **Firewall Service Token** to generate a
     fresh strong token. The service picks it up automatically on its
     next login.
   * Set **FreeSWITCH Agent Password** to something strong (≥12 chars,
     no spaces). Copy the value out into your `ODOO_PASSWORD`
     environment variable before saving, because the field gets
     masked back to `****` immediately after.
   * Adjust port lists and timeouts if you need to deviate from the
     defaults.
3. Connect → PBX → Firewall → **Whitelist**: add your trunk providers,
   office NAT exits, anything you don't want auto-banned. Save —
   `connect.firewall.agent._trigger_sync()` will POST to
   `/firewall/sync` immediately.
4. Connect → PBX → Firewall → **Agent Status**: should show the agent
   as *online* within one heartbeat interval (default 60 s).

## Daily operations

* **Active auto-bans** — they live only in the kernel. View them on
  the service's dashboard:
  `https://<your-host>/firewall/` (basic-auth with `DASHBOARD_USER` /
  `DASHBOARD_PASSWORD`). Each row has an Unban button.
* **From Odoo** — open `Connect → PBX → Firewall → Events`. Every row
  with **Event Type = Automatic Ban** gets a small unlock-icon
  button. Clicking it calls back into the service to remove the IP
  from `connect_fw_banned` and writes a `manual_unban_applied`
  audit record. The button hides itself as soon as the IP is no
  longer banned.
* **Permanent block** — `Connect → PBX → Firewall → Blacklist`, add an
  IP or CIDR. Useful for blocking entire VPS-provider subnets.

## Settings reference

| Setting | Default | Effect |
|---|---|---|
| Firewall Enabled | False | Master switch. When off, the service still runs but reports `firewall_enabled=False`. |
| Firewall Service URL | `http://host.docker.internal:8081` | Odoo posts `/firewall/sync` here. |
| Firewall Service Token | *generated* | Shared Bearer secret. ≥24 chars, `[A-Za-z0-9_-]` only. |
| FreeSWITCH Agent Password | *generated* | Portal-user password used for XML-RPC login. ≥12 chars, no spaces. |
| Heartbeat Interval | 60 s | How often the service pings Odoo. |
| Event Retention | 30 days | How long the audit log is kept; the daily cron prunes older. |
| Firewall TCP/UDP Ports | `5060,5061,5080,5081` | Where the chain hooks in. Must match the ports `sofia` actually listens on. |
| Auto-ban TTL | 86400 s (24 h) | How long an auto-ban stays in `connect_fw_banned`. |
| Trust TTL | 604800 s (7 d) | How long a successful registration buys trust. |
| Challenge Window | 30 s | `expire_short` lifetime. |
| Default-Deny TTL | 86400 s (24 h) | `expire_long` lifetime if the challenge is never answered. |

## Troubleshooting

```bash
# 1. Is the service alive?
curl -sk -u admin:<pw> https://<host>/firewall/healthz
curl -sk -u admin:<pw> https://<host>/firewall/api/heartbeat | jq

# 2. Is ESL really connected?
docker logs <firewall-container> | grep -E "ESL connected|Reconciler|AUTO-BAN"

# 3. Look at the actual kernel state.
ipset list connect_fw_banned
ipset list connect_fw_authenticated
iptables -L connect_fw_voip -v -n

# 4. Verify the chain is hooked into INPUT.
iptables -L INPUT -v -n | grep connect_fw_voip
```

If the agent stays *offline* in Odoo:

* check `ODOO_USER` / `ODOO_PASSWORD` — the easiest mistake is the
  password being rotated in Odoo but not redeployed to the container;
* check that the `freeswitch_agent` user is in `Role / Portal` and in
  the `FreeSWITCH Agent` group (the post-install migration takes care
  of this, but custom data-loading can disturb it);
* check that `/firewall/sync` is reachable from inside the Odoo
  container — Odoo sends notifications to this URL, not the service
  to Odoo.

If you see events arrive in Odoo but no auto-bans land in `ipset`:

* the container is running without `NET_ADMIN` — `ipset add` returns
  `Operation not permitted`, visible in the service logs;
* the kernel does not have the `ip_set` / `xt_set` modules
  available — typical on hardened/minimal hosts. `modprobe ip_set`
  on the host fixes it.

## Architecture-level reference

See `specs/decisions/014-freeswitch-firewall-service.md` for the
design decisions behind this stack (six-table ipset model, direct
HTTP control plane, hardcoded UA blacklist, single-instance, IPv4-only).
