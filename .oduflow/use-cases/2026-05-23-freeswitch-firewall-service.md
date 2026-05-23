# freeswitch-firewall-service — 2026-05-23

**Branch:** `litnimax/fail2ban-odoo-integration`
**Goal:** Design, implement and end-to-end validate a SIP brute-force firewall — an out-of-process Python service paired with the `connect_freeswitch` Odoo module, ipset/iptables on the host kernel, a Lit dashboard, and full live verification against a real FreeSWITCH plus external SIPp.
**Related files/PR:** PR https://github.com/oduist/connect_addons_ng/pull/58 (ADR-014, `connect_freeswitch/deploy/firewall/`, models `connect.firewall.*`).

## Context

The Odoo module was being authored in this repository while a real FreeSWITCH was needed in parallel to: (1) ship code changes to a live database, (2) experiment with `mod_event_socket` events from the wire to confirm sofia event names and headers, (3) run the Python service in `host_mode` with `NET_ADMIN` so `ipset`/`iptables` could touch the host kernel, and (4) replay edits quickly across many cycles.

Oduflow was used as the only deployment surface for this work — provisioning an ephemeral Odoo environment with the FreeSWITCH service preset, hot-applying module changes via `pull_and_apply`, manipulating the auxiliary firewall service through `create_service` / `delete_service` / `get_service_logs`, doing live database inspections via `run_odoo_shell`, and running raw shell probes inside the FreeSWITCH container via `run_service_command`. This file keeps only the milestone calls that show the dynamics — many minor identical sync verifications are omitted.

---

## Step 1. Bring up a fresh Odoo environment on the working branch

**Tool:** `mcp__oduflow_oduist__create_environment`

**Arguments:**
```json
{
  "branch": "litnimax/fail2ban-odoo-integration",
  "env_name": "fw",
  "template_name": "fs19-dev"
}
```

**Result:**
```
Environment provisioned successfully!
Environment: fw
Git Branch: litnimax/fail2ban-odoo-integration
URL: https://fw.team.dev.oduist.com
Odoo Container: oduflow-fw-odoo
Database: oduflow_2_fw
Workspace: /srv/oduflow/team_2/workspaces/fw
Template: fs19-dev
Creation time: 32.1s
```

**Observation:** The `fs19-dev` template snapshot still pointed at a pre-rename `connect.user.username` field, so the very first `upgrade_odoo_modules connect_freeswitch` failed validating an inherited view. Upgrading both modules together (`connect,connect_freeswitch`) ran the `connect` 19.0.3.1.0 migration that dropped the obsolete column and then the FreeSWITCH module loaded clean — that became the standing recipe for the rest of the session.

---

## Step 2. Pull + apply cycles to drive iterations on the Odoo side

**Tool:** `mcp__oduflow_oduist__pull_and_apply`

**Arguments:**
```json
{ "env_name": "fw" }
```

**Result (selected, after the 19.0.1.8.3 commit added migrations):**
```
Upgraded modules: connect_freeswitch Container restarted.
Upgraded: connect_freeswitch
Changed files (4):
  - connect_freeswitch/__init__.py
  - connect_freeswitch/__manifest__.py
  - connect_freeswitch/migrations/19.0.1.8.3/post-migrate.py
  - connect_freeswitch/models/settings.py
...
2026-05-21 08:02:27,467 INFO oduflow_2_fw odoo.modules.migration: module connect_freeswitch: Running upgrade [19.0.1.8.3>] post-migrate 
2026-05-21 08:02:28,056 INFO oduflow_2_fw odoo.upgrade.connect_freeswitch.19.0.1.8.3.post-migrate: Firewall setup completed during upgrade
```

**Observation:** Every iteration on the Odoo side was a `git push` followed by a single `pull_and_apply`. The custom `19.0.1.8.3/post-migrate.py` ran the same `setup_firewall(env)` function as `post_init_hook`, so upgrades against template-installed copies got the portal-user re-classed into `Role/Portal`, secrets generated and the agent singleton created. Many subsequent sync calls (`+0 -0`) are dropped from this log.

---

## Step 3. Probe the live ESL bus from inside the FreeSWITCH container

**Tool:** `mcp__oduflow_oduist__run_service_command`

**Arguments:**
```json
{
  "name": "fs",
  "command": "sh -c \"echo <base64 of /tmp/esl_probe.py> | base64 -d > /tmp/esl_probe.py && python3 /tmp/esl_probe.py 2>&1 | head -200\""
}
```

**Result (excerpt — the listener captured the first wave of real events):**
```
LISTENING
>>> CUSTOM / sofia%3A%3Apre_register
    from-host: team.dev.oduist.com
    from-user: 102
    to-user: 102
    contact: ... received=94.243.71.117:43029 ...
>>> CUSTOM / sofia%3A%3Aregister_attempt
    auth-result: FORBIDDEN
    realm: team.dev.oduist.com
>>> CUSTOM / sofia%3A%3Aregister_failure
>>> CUSTOM / sofia%3A%3Awrong_call_state
    ...
    network_ip: 94.243.71.117
    network_port: 44622
    from_user: sipp
DONE
```

**Observation:** Three concrete findings that drove the next code commit: ESL `text/event-plain` bodies are URL-encoded; `wrong_call_state` carries the IP as `network_ip` (lowercase, underscore), not `Network-Ip`; `register_attempt` with `auth-result=FORBIDDEN` is the real failure carrier on this FreeSWITCH build. All three were folded into `esl_handler.py` with a single follow-up `pull_and_apply` (1.0.6).

---

## Step 4. Create the auxiliary firewall service (host network + NET_ADMIN + volume)

**Tool:** `mcp__oduflow_oduist__create_volume` then `mcp__oduflow_oduist__create_service`

**Arguments:**
```json
{
  "name": "firewall",
  "image": "oduist/freeswitch-firewall:1.0.9",
  "port": 48088,
  "host_mode": true,
  "net_admin": true,
  "volumes": "firewall-cache:/var/lib/connect-firewall",
  "env_vars": "ODOO_URL=https://fw.team.dev.oduist.com,ODOO_DB=oduflow_2_fw,ODOO_USER=freeswitch_agent,ODOO_PASSWORD=***,FS_ESL_HOST=127.0.0.1,FS_ESL_PORT=8021,HTTP_BIND_HOST=0.0.0.0,HTTP_BIND_PORT=48088,DASHBOARD_USER=admin,DASHBOARD_PASSWORD=***,LOG_LEVEL=INFO"
}
```

**Result:**
```
Service created successfully!
Name: firewall
Container: oduflow-svc-firewall
Image: oduist/freeswitch-firewall:1.0.9
URL: https://firewall.team.dev.oduist.com
Volumes: firewall-cache:/var/lib/connect-firewall:rw
```

**Observation:** Three things were learned across multiple delete/create iterations and are codified in this final form: (1) `host_mode=true` alone does not grant `NET_ADMIN`, the explicit `net_admin=true` parameter is required for `ipset` to work; (2) the service must bind on `0.0.0.0` for Traefik to reach it in the shared docker network — `127.0.0.1` in host network is invisible from another container; (3) the chosen port has to avoid colliding with Traefik's own listener, hence `48088` (Traefik proxies `https://firewall.team.dev.oduist.com` → host:48088). Real values for `ODOO_PASSWORD` and `DASHBOARD_PASSWORD` are masked in this log.

---

## Step 5. Read the firewall service logs to watch event flow

**Tool:** `mcp__oduflow_oduist__get_service_logs`

**Arguments:**
```json
{ "name": "firewall", "n_lines": 20 }
```

**Result (after the URL-decode + IP-extractor fixes landed):**
```
2026-05-21 14:53:42,707 INFO connect_firewall_service.esl_handler: AUTO-BAN 94.243.71.117 (user=sipp, ua=, sofia::wrong_call_state)
2026-05-21 14:53:42,889 INFO connect_firewall_service.esl_handler: AUTO-BAN 94.243.71.117 (user=sipp, ua=, sofia::wrong_call_state)
2026-05-21 14:53:43,070 INFO connect_firewall_service.esl_handler: AUTO-BAN 94.243.71.117 (user=sipp, ua=, sofia::wrong_call_state)
...
2026-05-21 14:53:43,077 INFO httpx: HTTP Request: POST https://fw.team.dev.oduist.com/jsonrpc/ "HTTP/1.1 200 OK"
```

**Observation:** First confirmation that an external sipp INVITE on `148.251.17.221:5080` flowed all the way through: kernel ipset, esl_handler, `report_event` POST to Odoo. The three identical log lines also revealed the duplicate-AUTO-BAN problem — sofia emits both `register_attempt(FORBIDDEN)` and `register_failure` for the same failed attempt — and led to the `is_member()` dedup in the next commit.

---

## Step 6. Inspect Odoo state directly when something didn't match expectations

**Tool:** `mcp__oduflow_oduist__run_odoo_shell`

**Arguments:**
```json
{
  "env_name": "fw",
  "python_code": "pwd = self.env['connect.settings'].sudo().get_param('freeswitch_agent_password') or ''\nprint('freeswitch_agent password:', pwd)\nprint('len:', len(pwd))"
}
```

**Result:**
```
freeswitch_agent password: aaaaa
len: 5
```

**Observation:** Login to Odoo from the freshly redeployed service started failing with "Odoo login returned False". A quick shell read showed the password had been manually overwritten to `aaaaa` through the UI during earlier testing. Mitigated in the same session by generating a fresh `secrets.token_urlsafe(24)` value, writing it both to `connect.settings` and to the portal user record, and recreating the service container with the new `ODOO_PASSWORD`. The value is masked in this log (`***`).

---

## Step 7. End-to-end verification — IP visible in Odoo events with Unban capability

**Tool:** `mcp__oduflow_oduist__run_odoo_shell`

**Arguments:**
```json
{
  "env_name": "fw",
  "python_code": "events = self.env['connect.firewall.event'].search([], order='ts desc', limit=10)\nfor e in events:\n    print(f'  {e.ts} | {e.event_type:25s} | ip={e.ip:18s} | user={e.account_id} | {e.details}')"
}
```

**Result:**
```
Total events: 1
  2026-05-21 15:01:27 | auto_ban                  | ip=94.243.71.117      | user=sipp | sofia::wrong_call_state
```

**Observation:** Confirms the full chain works after the `_first_dict` helper landed on the Odoo side: sipp INVITE → sofia `wrong_call_state` → service `AUTO-BAN` → kernel `ipset connect_fw_banned` → service `report_event` → Odoo `connect.firewall.event` row. From this moment the dashboard's Unban button and the Odoo events Unban button were exercised against the same record without further code changes.

---

## Outcome

Oduflow was the single development surface for the whole task. The dynamics looked like this:

1. **Provision once** (`create_environment fw`) with `fs19-dev` to get a real FreeSWITCH next to a real Odoo on a real public IP — letting external SIPp traffic actually arrive at the box.
2. **Iterate on the Odoo module** with `git push` + `pull_and_apply`. Each iteration triggered the matching migration if needed; the loop was tight enough that ten module versions (`19.0.1.8.0` → `19.0.1.8.12`) were exercised in the session.
3. **Iterate on the Python service** outside Oduflow (`docker buildx ... --push`), then run `delete_service` + `create_service` with the new image tag. Five service image tags (`1.0.5` → `1.0.9`) made it through this loop, each one fixing a concrete bug exposed by the previous run's `get_service_logs`.
4. **Reach into FreeSWITCH and Odoo when blind** — `run_service_command` against the `fs` container ran a Python ESL probe whose output unlocked the URL-decode and `network_ip`/`from_user` discoveries; `run_odoo_shell` was used both to inspect mismatches (the manually-typed `aaaaa` password) and to drive the same scenarios that the eventual users would (creating whitelist rows, reading event rows, validating secret strength).

Net result: the firewall now bans real sipp INVITE / Telephone 1.6 traffic from an external public IP, the dashboard shows live state, the Odoo audit log captures one row per actual incident (dedup confirmed), and the Unban flow works from both the dashboard and from inside the Events list in Odoo. PR https://github.com/oduist/connect_addons_ng/pull/58 carries the code.
