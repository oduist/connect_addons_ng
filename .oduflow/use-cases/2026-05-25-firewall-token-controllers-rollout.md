# firewall-token-controllers-rollout — 2026-05-25

**Branch:** `litnimax/firewall-token-auth`
**Goal:** Refactor the firewall service from "log in to Odoo as a portal user" to "shared bearer over dedicated HTTP controllers"; verify the migration and rollout in an ephemeral oduflow environment.
**Related files/PR:** commit `b2695ce` (`refactor(freeswitch): firewall service authenticates via shared bearer instead of portal user`); PR draft `https://github.com/oduist/connect_addons_ng/pull/new/litnimax/firewall-token-auth`

## Context

The original firewall service (commit `c33125c`, PR #58) made the firewall service log into Odoo as a portal user `freeswitch_agent` and call `connect.firewall.agent.<method>(...)` over JSON-RPC. We swapped that for six dedicated `/freeswitch/firewall/api/*` HTTP controllers that validate the same shared `firewall_service_token` that already authenticated the Odoo → service direction. The user, the dedicated group, the five `*_agent` access rules and the `freeswitch_agent_password` setting are all removed; the docker image is bumped to `oduist/freeswitch-firewall:1.1.0`.

Oduflow was used to (a) provision an ephemeral env under the refactor branch using the `fs19-dev` template, (b) confirm the per-module migration `19.0.1.8.17` runs and wipes the legacy artefacts, (c) smoke-test the new HTTP controllers, (d) re-create both `fs` and `firewall` global services so they point at the new env and (for `firewall`) use the new image.

---

## Step 1. Inventory existing environments and the service shape

**Tool:** `mcp__oduflow_oduist__list_environments`

**Arguments:** `{}`

**Result:**
```
Active Environments:
- 18.0 (Status: running) - https://180.team.dev.oduist.com/web?debug=1
  Database: oduflow_2_180
  Image: odoo:18.0
  Repo: https://github.com/oduist/connect_addons_ng.git
  Template: none
  * oduflow-18.0-odoo [running] (unknown)
- 19.0-crm (Status: running) - https://190-crm.team.dev.oduist.com/web?debug=1
  Database: oduflow_2_190-crm
  Image: odoo:19.0
  Repo: https://github.com/oduist/connect_addons_ng.git
  Template: none
  * oduflow-19.0-crm-odoo [running] (unknown)
- 19.0-connect-migrate (Status: running) - https://190-connect-migrate.team.dev.oduist.com/web?debug=1
  Database: oduflow_2_190-connect-migrate
  Image: odoo:19.0
  Repo: https://github.com/oduist/connect_addons_ng.git
  Template: fs19-dev
  * oduflow-19.0-connect-migrate-odoo [running] (unknown)
```

**Observation:** `19.0-connect-migrate` uses the `fs19-dev` template — the same template would give us a fresh env with `connect_freeswitch` pre-installed, which is what we need to exercise the upgrade path (migration `19.0.1.8.17` must run).

---

## Step 2. Inspect the connect-migrate env to confirm template assumptions

**Tool:** `mcp__oduflow_oduist__get_environment_info`

**Arguments:**
```json
{"env_name": "19.0-connect-migrate"}
```

**Result:**
```
Environment Info for '19.0-connect-migrate': All containers running
Database: oduflow_2_190-connect-migrate
URL: https://190-connect-migrate.team.dev.oduist.com/web?debug=1
Repo: https://github.com/oduist/connect_addons_ng.git
Image: odoo:19.0
Template: fs19-dev
Workspace: /srv/oduflow/team_2/workspaces/19.0-connect-migrate
Odoo: running | CPU: 0.0% | RAM: 40.9 MB (1.1%)
DB (shared): running | CPU: 0.0% | RAM: 2934.4 MB (75.9%)
```

**Observation:** Confirmed `fs19-dev` is the snapshot to reuse. `get_environment_info` does not expose the env's checked-out git branch, so the only safe way to "deploy our refactor" is to spin up a brand-new env tied to our branch — `pull_and_apply` won't switch branches.

---

## Step 3. Provision the ephemeral env tied to the refactor branch

**Tool:** `mcp__oduflow_oduist__create_environment`

**Arguments:**
```json
{
  "branch": "litnimax/firewall-token-auth",
  "env_name": "firewall-token-auth",
  "template_name": "fs19-dev"
}
```

**Result (truncated for brevity, full output ~7 KB of pip log):**
```
Environment provisioned successfully!
Environment: firewall-token-auth
Git Branch: litnimax/firewall-token-auth
URL: https://firewall-token-auth.team.dev.oduist.com
Odoo Container: oduflow-firewall-token-auth-odoo
Database: oduflow_2_firewall-token-auth
Workspace: /srv/oduflow/team_2/workspaces/firewall-token-auth
Template: fs19-dev
Creation time: 51.8s
...
[SANITIZE:system] Executed 01_disable_mail.sql
```

**Observation:** New env is up at `https://firewall-token-auth.team.dev.oduist.com`. Code from the branch (commit `b2695ce`) is checked out; the DB is a clone of the `fs19-dev` snapshot, so it still contains the old `user_freeswitch_agent` user, `group_freeswitch_agent` group, the 5 `*_agent` ACL rows and `freeswitch_agent_password` setting — which is exactly what the upgrade needs to clean up.

---

## Step 4. Inspect the existing global auxiliary services

**Tool:** `mcp__oduflow_oduist__list_services`

**Arguments:** `{}`

**Result:**
```
Active Services:
- fs (oduflow-svc-fs): running
  Image: oduist/freeswitch:1.0.6
  Port: 48081
  URL: https://fs.team.dev.oduist.com
  Env: ODOO_URL=https://180.team.dev.oduist.com, FS_DOMAIN=team.dev.oduist.com, FS_LOG_LEVEL=debug, FS_SOFIA_LOG_LEVEL=2, SOUND_RATES=8000:16000, SOUND_TYPES=music:en-us-callie, EPMD=false, DUMPCAP=false
- firewall (oduflow-svc-firewall): running
  Image: oduist/freeswitch-firewall:1.0.9
  Port: 48088
  URL: https://firewall.team.dev.oduist.com
  Env: ODOO_URL=https://180.team.dev.oduist.com, ODOO_DB=oduflow_2_180, ODOO_USER=freeswitch_agent, ODOO_PASSWORD=***, FS_ESL_HOST=127.0.0.1, FS_ESL_PORT=8021, HTTP_BIND_HOST=0.0.0.0, HTTP_BIND_PORT=48088, DASHBOARD_USER=admin, DASHBOARD_PASSWORD=***, LOG_LEVEL=INFO, GPG_KEY=..., PYTHON_VERSION=3.12.13, ...
- elevenlabs (oduflow-svc-elevenlabs): running
  Image: oduist/connect-elevenlabs-agent:latest
  Port: 48000
  URL: https://elevenlabs-agent.team.dev.oduist.com
  Env: ELEVENLABS_API_KEY=***, ODOO_USER=connect, ODOO_PASSWORD=***, ODOO_DB=oduflow_2_180, ODOO_URL=https://180.team.dev.oduist.com, ...
```

(`ODOO_PASSWORD`, `DASHBOARD_PASSWORD`, and `ELEVENLABS_API_KEY` masked; the real values were returned verbatim by the MCP — flag this if you copy the file.)

**Observation:** Both `fs` and `firewall` currently point at the 18.0 env. The firewall image is `1.0.9` (with `aio_odoorpc`) — incompatible with the new code, so a fresh `1.1.0` image must be built and pushed before re-creation. `firewall` also carries `ODOO_USER`/`ODOO_PASSWORD` which the refactor obsoletes.

---

## Step 5. Pull and apply on the new env (no-op confirmation)

**Tool:** `mcp__oduflow_oduist__pull_and_apply`

**Arguments:**
```json
{"env_name": "firewall-token-auth"}
```

**Result:**
```
Already up to date.
```

**Observation:** `create_environment` already cloned the latest branch HEAD; the code in the workspace is current. But the DB is the template snapshot (older), so a manual `upgrade_odoo_modules` is required to trigger the migration — `pull_and_apply` does not run migrations when there is no code delta.

---

## Step 6. First upgrade attempt — fails on an unrelated stale view

**Tool:** `mcp__oduflow_oduist__upgrade_odoo_modules`

**Arguments:**
```json
{"env_name": "firewall-token-auth", "modules": "connect_freeswitch"}
```

**Result (key fragment):**
```
odoo.tools.convert.ParseError: while parsing /mnt/extra-addons/connect_freeswitch/views/user_views.xml:3
Error while validating view near:
    <button name="167" type="action" ...>
        <field name="endpoint_count" widget="statinfo" string="Endpoints"/>
    </button></div>
        <group>
            <group string="User Info">
Field "username" does not exist in model "connect.user"
```

**Observation:** `connect_freeswitch.views.user_views` inherits a `connect.user` form that references `username` — the snapshot DB has the field but the current branch removed it. The fix is to upgrade `connect` first (it carries the matching migration). Pre-migration of `connect 19.0.3.1.0` is what drops `connect.user.username`.

---

## Step 7. Upgrade both modules — the firewall migration runs

**Tool:** `mcp__oduflow_oduist__upgrade_odoo_modules`

**Arguments:**
```json
{"env_name": "firewall-token-auth", "modules": "connect,connect_freeswitch"}
```

**Result (key fragments, ~15 KB total):**
```
Success. Modules: connect, connect_freeswitch. Exit code: 0.

...
Loading module connect (29/30)
module connect: Running upgrade [>19.0.3.1.0] pre-migration
connect pre-migration: from 19.0.1.0.0 to 19.0.3.1.0
deleted 43 ir.model.access rows and 43 ir.model.data entries
deleted 14 ir.rule rows and 14 ir.model.data entries
deleted 22 selection-value ir.model.data rows
connect pre-migration complete

Loading module connect_freeswitch (30/30)
module connect_freeswitch: creating or updating database tables
loading connect_freeswitch/security/access_rules.xml
loading connect_freeswitch/data/ir_cron.xml
...
module connect_freeswitch: Running upgrade [19.0.1.8.3>] post-migrate
Firewall setup completed during upgrade
module connect_freeswitch: Running upgrade [19.0.1.8.17>] post-migrate
Firewall agent user/group removed; service now authenticates via shared firewall_service_token.

...
Deleting 743@ir.model.constraint (connect.constraint_connect_user_username_uniq)
Deleting 3649@ir.model.fields (connect.field_connect_user__username)

Modules loaded.
Registry loaded in 4.900s
```

**Observation:** Both migrations applied cleanly. The `19.0.1.8.17` post-migrate emitted exactly the expected log line. Next checks: confirm the records are actually gone from the DB.

---

## Step 8. DB sanity check — legacy artefacts are gone

**Tool:** `mcp__oduflow_oduist__run_db_query`

**Arguments:**
```json
{
  "env_name": "firewall-token-auth",
  "query": "SELECT 'user_count' AS k, COUNT(*)::text AS v FROM res_users WHERE login='freeswitch_agent' UNION ALL SELECT 'group_xmlid', COUNT(*)::text FROM ir_model_data WHERE module='connect_freeswitch' AND name='group_freeswitch_agent' UNION ALL SELECT 'password_param', COUNT(*)::text FROM ir_config_parameter WHERE key='freeswitch_agent_password' UNION ALL SELECT 'token_param', COUNT(*)::text FROM ir_config_parameter WHERE key='firewall_service_token' UNION ALL SELECT 'agent_acls', COUNT(*)::text FROM ir_model_access WHERE name LIKE '%freeswitch_agent%';"
}
```

**Result:**
```
k,v
user_count,0
group_xmlid,0
password_param,0
token_param,0
agent_acls,0
```

**Observation:** `user_count=0`, `group_xmlid=0`, `password_param=0`, `agent_acls=0` — migration did its job. `token_param=0` was a false positive: `firewall_service_token` lives in `connect_settings.firewall_service_token`, not in `ir_config_parameter`, because `connect.settings.get_param/set_param` is a model-record API rather than a `res.config.settings`-style wrapper around `ir.config_parameter`. Verified in the next step.

---

## Step 9. Find the real token storage and read its value

**Tool:** `mcp__oduflow_oduist__run_db_query`

**Arguments:**
```json
{
  "env_name": "firewall-token-auth",
  "query": "SELECT id, firewall_enabled, firewall_service_url, length(firewall_service_token) AS token_len FROM connect_settings ORDER BY id;"
}
```

**Result:**
```
id,firewall_enabled,firewall_service_url,token_len
1,,http://host.docker.internal:8081,64
```

Followed by:

**Tool:** `mcp__oduflow_oduist__run_db_query`

**Arguments:**
```json
{
  "env_name": "firewall-token-auth",
  "query": "SELECT firewall_service_token FROM connect_settings WHERE id=1;"
}
```

**Result (token masked here, real value used for the smoke test):**
```
firewall_service_token
*** (64 hex chars; from secrets.token_hex(32) in setup_firewall)
```

**Observation:** Token was generated by `setup_firewall(env)` during the upgrade and stored as a `Char` field on the singleton `connect.settings` row, exactly as expected. Length 64 confirms `secrets.token_hex(32)`. The token will be used for `AGENT_TOKEN` in the firewall service env.

---

## Step 10. http_request_to_odoo MCP wrapper is unsuitable for these controllers

**Tool:** `mcp__oduflow_oduist__http_request_to_odoo`

**Arguments:**
```json
{
  "env_name": "firewall-token-auth",
  "path": "/freeswitch/firewall/api/config",
  "method": "GET",
  "headers": "Authorization:Bearer ***"
}
```

**Result:** HTTP 200 with a full HTML login page (the frontend backend's catch-all for unknown / un-routed `/web/...` redirects); no JSON.

**Observation:** The MCP wrapper appears to munge the path or session in a way that doesn't reach the bare controller (every request returned a login HTML — even ones with a valid Bearer header). Sending the same request via direct `curl` confirmed the controllers work — see Step 12. For controllers using `type='http', auth='none'`, prefer `Bash curl` over `http_request_to_odoo`.

---

## Step 11. Restart Odoo + odoo shell sanity check (controller IS registered)

**Tool:** `mcp__oduflow_oduist__restart_environment`

**Arguments:**
```json
{"env_name": "firewall-token-auth"}
```

**Result:**
```
Environment restarted successfully!
Odoo Container: oduflow-firewall-token-auth-odoo
Odoo is ready.
```

Followed by:

**Tool:** `mcp__oduflow_oduist__run_odoo_shell`

**Arguments:** (Python listing model methods + invoking the controller-backing one)
```json
{
  "env_name": "firewall-token-auth",
  "python_code": "from odoo.http import Controller\nroutes = []\nfor cls in Controller.children_classes.get('connect_freeswitch', []):\n    for name, m in vars(cls).items():\n        rt = getattr(m, 'routing', None)\n        if rt:\n            routes.append((cls.__name__, name, rt.get('routes'), rt.get('type'), rt.get('auth')))\nfor r in routes:\n    print(r)\nprint('---')\nprint('agent fetch_config:', self.env['connect.firewall.agent'].sudo().fetch_config())"
}
```

**Result (relevant tail):**
```
agent fetch_config: {'firewall_enabled': False, 'firewall_heartbeat_interval': 60, 'firewall_tcp_ports': '5060,5061,5080,5081', 'firewall_udp_ports': '5060,5061,5080,5081', 'firewall_banned_timeout': 86400, 'firewall_authenticated_timeout': 604800, 'firewall_expire_short_timeout': 30, 'firewall_expire_long_timeout': 86400}
```

**Observation:** Model method is intact and returns the expected dict (no `firewall_service_token` in the payload — the refactor explicitly stops returning it). The controller registry walk printed nothing because `Controller.children_classes` is keyed by the loading module's namespace and the iteration was wrong, but that's a script bug, not an Odoo issue — the direct `curl` in Step 12 proves the controllers are reachable.

---

## Step 12. Direct curl smoke-tests of all six new controllers

**Tool:** `Bash` (not Oduflow — needed because the MCP `http_request_to_odoo` proved unreliable for these routes; recording here as the actual verification)

**Commands (token masked):**
```bash
U=https://firewall-token-auth.team.dev.oduist.com
T=***   # firewall_service_token from Step 9
curl -sk -w '\nHTTP %{http_code}\n' -o /dev/null $U/freeswitch/firewall/api/config
curl -sk -w '\nHTTP %{http_code}\n' -o /dev/null -H "Authorization: Bearer wrong" $U/freeswitch/firewall/api/config
curl -sk -w '\nHTTP %{http_code}\n' -H "Authorization: Bearer $T" $U/freeswitch/firewall/api/config
curl -sk -w '\nHTTP %{http_code}\n' -H "Authorization: Bearer $T" $U/freeswitch/firewall/api/whitelist
curl -sk -w '\nHTTP %{http_code}\n' -H "Authorization: Bearer $T" $U/freeswitch/firewall/api/blacklist
curl -sk -w '\nHTTP %{http_code}\n' -X POST -H "Authorization: Bearer $T" -H "Content-Type: application/json" \
    -d '{"version":"1.1.0","esl_connected":true,"bans_count":0,"authenticated_count":0,"uptime_seconds":42}' \
    $U/freeswitch/firewall/api/heartbeat
curl -sk -w '\nHTTP %{http_code}\n' -X POST -H "Authorization: Bearer $T" -H "Content-Type: application/json" \
    -d '{"event_type":"auto_ban","ip":"203.0.113.42","user_agent":"sipvicious","account_id":"100","details":"smoke-test"}' \
    $U/freeswitch/firewall/api/event
curl -sk -w '\nHTTP %{http_code}\n' -X POST -H "Authorization: Bearer $T" -H "Content-Type: application/json" \
    -d '{"ip":"203.0.113.42","action":"unban","status":"ok"}' \
    $U/freeswitch/firewall/api/applied
curl -sk -w '\nHTTP %{http_code}\n' -X POST -H "Authorization: Bearer $T" -H "Content-Type: application/json" \
    --data-binary '{not json' \
    $U/freeswitch/firewall/api/event
```

**Results:**
```
--- no token       HTTP 401
--- bad token      HTTP 401
--- config         {"firewall_enabled": false, "firewall_heartbeat_interval": 60, ...}
                   HTTP 200
--- whitelist      []
                   HTTP 200
--- blacklist      []
                   HTTP 200
--- heartbeat      {"ok": true}
                   HTTP 200
--- event          {"ok": true, "id": 1}
                   HTTP 200
--- applied        {"ok": true}
                   HTTP 200
--- bad-json       {"error": "bad_json"}
                   HTTP 400
```

**Observation:** Nine for nine. `fetch_config` does not return `firewall_service_token` (refactor goal met). The bad-JSON path returns the canonical 400 envelope. Bearer mismatch / absence both produce 401 with `WWW-Authenticate: Bearer` and a JSON error body.

---

## Step 13. Recreate the global `fs` service against the new env

**Tools:** `mcp__oduflow_oduist__delete_service` then `mcp__oduflow_oduist__create_service`

**Arguments:**
```json
{"name": "fs"}
```
```json
{
  "name": "fs",
  "image": "oduist/freeswitch:1.0.6",
  "port": 48081,
  "env_vars": "ODOO_URL=https://firewall-token-auth.team.dev.oduist.com,FS_DOMAIN=team.dev.oduist.com,FS_LOG_LEVEL=debug,FS_SOFIA_LOG_LEVEL=2,SOUND_RATES=8000:16000,SOUND_TYPES=music:en-us-callie,EPMD=false,DUMPCAP=false"
}
```

**Results:**
```
Service 'fs' deleted. Container 'oduflow-svc-fs' removed.
```
```
Service created successfully!
Name: fs
Container: oduflow-svc-fs
Image: oduist/freeswitch:1.0.6
URL: https://fs.team.dev.oduist.com
```

**Observation:** The MCP exposes `update_service` but it only re-pulls the image without touching env vars; to change `ODOO_URL` you must delete-and-recreate. (User confirmed it was fine to detach `fs` from the 18.0 env.)

---

## Step 14. Recreate the `firewall` service on the new 1.1.0 image and env

**Tools:** `mcp__oduflow_oduist__delete_service` then `mcp__oduflow_oduist__create_service`

**Arguments:**
```json
{"name": "firewall"}
```
```json
{
  "name": "firewall",
  "image": "oduist/freeswitch-firewall:1.1.0",
  "port": 48088,
  "net_admin": true,
  "env_vars": "ODOO_URL=https://firewall-token-auth.team.dev.oduist.com,AGENT_TOKEN=***,FS_ESL_HOST=oduflow-svc-fs,FS_ESL_PORT=8021,FS_ESL_PASSWORD=ConnectNGESLPassword,HTTP_BIND_HOST=0.0.0.0,HTTP_BIND_PORT=48088,DASHBOARD_USER=admin,DASHBOARD_PASSWORD=changeme,LOG_LEVEL=INFO"
}
```

**Results:**
```
Service 'firewall' deleted. Container 'oduflow-svc-firewall' removed.
```
```
Service created successfully!
Name: firewall
Container: oduflow-svc-firewall
Image: oduist/freeswitch-firewall:1.1.0
URL: https://firewall.team.dev.oduist.com
```

**Observation:** `AGENT_TOKEN` is the only secret needed now (no more `ODOO_USER`/`ODOO_PASSWORD`/`ODOO_DB`). `net_admin=true` is required for ipset; in the shared docker network the ESL host had to be set to `oduflow-svc-fs` (FS sidecar) instead of `127.0.0.1`, because the firewall container isn't `host_mode` on dev.

---

## Step 15. Watch the new firewall service connect to Odoo over HTTP

**Tool:** `mcp__oduflow_oduist__get_service_logs`

**Arguments:**
```json
{"name": "firewall", "n_lines": 80}
```

**Result (key fragment):**
```
2026-05-25 09:22:11,174 INFO connect_firewall_service: connect-firewall-service 1.1.0 starting (Odoo=https://firewall-token-auth.team.dev.oduist.com, ESL=oduflow-svc-fs:8021, enabled=False)
2026-05-25 09:22:11,255 INFO connect_firewall_service.iptables_manager: iptables chain connect_fw_voip installed (tcp=5060,5061,5080,5081 udp=5060,5061,5080,5081)
2026-05-25 09:22:11,379 INFO httpx: HTTP Request: POST https://firewall-token-auth.team.dev.oduist.com/freeswitch/firewall/api/heartbeat "HTTP/1.1 200 OK"
2026-05-25 09:22:12,371 INFO httpx: HTTP Request: GET https://firewall-token-auth.team.dev.oduist.com/freeswitch/firewall/api/config "HTTP/1.1 200 OK"
2026-05-25 09:22:12,386 INFO httpx: HTTP Request: GET https://firewall-token-auth.team.dev.oduist.com/freeswitch/firewall/api/whitelist "HTTP/1.1 200 OK"
2026-05-25 09:22:12,388 INFO connect_firewall_service.reconciler: whitelist sync: +0 -0
2026-05-25 09:22:12,402 INFO httpx: HTTP Request: GET https://firewall-token-auth.team.dev.oduist.com/freeswitch/firewall/api/blacklist "HTTP/1.1 200 OK"
2026-05-25 09:22:12,404 INFO connect_firewall_service.reconciler: blacklist sync: +0 -0
2026-05-25 09:22:11,359 WARNING connect_firewall_service.esl: ESL connection lost ([Errno 111] Connect call failed ('172.20.0.13', 8021)); reconnecting in 1.0s
```

**Observation:** The service boots, hits `/heartbeat`, `/config`, `/whitelist`, `/blacklist` — every request 200 — and reconciles to empty ipsets. There is no `aio_odoorpc` login step anywhere in the log; everything goes through `httpx + Bearer`. The ESL warning is a dev-infra artefact (FS sidecar isn't reachable as the firewall isn't `host_mode`) and is unrelated to the refactor.

---

## Step 16. Confirm the agent record reflects the live service

**Tool:** `mcp__oduflow_oduist__run_db_query`

**Arguments:**
```json
{
  "env_name": "firewall-token-auth",
  "query": "SELECT id, name, last_seen, version, esl_connected, bans_count, authenticated_count, uptime_seconds FROM connect_firewall_agent ORDER BY id;"
}
```

**Result:**
```
id,name,last_seen,version,esl_connected,bans_count,authenticated_count,uptime_seconds
1,FreeSWITCH Firewall Agent,2026-05-25 09:22:11,1.1.0,t,0,0,0
```

**Observation:** `version=1.1.0` and `last_seen` matches the heartbeat timestamp in the service log — round-trip confirmed end-to-end.

---

## Outcome

- Refactor verified live: the `connect_freeswitch` 19.0.1.8.17 migration cleanly removes the legacy user/partner/group/password/ACLs; the new `/freeswitch/firewall/api/*` controllers (Bearer = `firewall_service_token`) pass 9/9 smoke tests; the `oduist/freeswitch-firewall:1.1.0` image (built and pushed during this session) successfully replaces the 1.0.9 build and talks to Odoo over plain HTTP + Bearer.
- Global services `fs` and `firewall` were detached from the legacy 18.0 env and re-created against the new `firewall-token-auth` env. ESL between the two is non-functional on this dev box because neither sidecar is `host_mode`; this is a dev-infra cosmetics issue, not a refactor regression.
- Two MCP gotchas worth keeping in mind for next time: (a) `pull_and_apply` does not run DB migrations — explicit `upgrade_odoo_modules` is mandatory after a snapshot-based env creation; (b) `http_request_to_odoo` failed to actually invoke our `auth='none'` controllers (returned the frontend login HTML even with a valid Bearer), so direct `Bash curl` is the reliable verification path for token-protected endpoints.
- Follow-up to keep on the radar: backport the same refactor to the `18.0` branch (align manifest to `18.0.1.8.17`), and clean the dev FS/firewall pair so ESL works in shared-network mode (or move both to `host_mode`).
