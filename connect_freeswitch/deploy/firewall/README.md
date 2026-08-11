# connect-firewall-service

FreeSWITCH SIP brute-force protection service paired with the
`connect_freeswitch` Odoo module. See `specs/decisions/014-freeswitch-firewall-service.md`
for the architecture and `specs/decisions/015-firewall-token-controllers.md`
for the current auth model.

## Build

```
docker build --platform linux/amd64 \
    --provenance=false --sbom=false \
    -t oduist/freeswitch-firewall:2.1.1 \
    -t oduist/freeswitch-firewall:latest \
    .
docker push oduist/freeswitch-firewall:2.1.1
docker push oduist/freeswitch-firewall:latest
```

## Tests

Unit tests for the pure helpers (IP normalization, ESL IP extraction)
live in `tests/` and are excluded from the Docker image:

```
python -m venv .venv && . .venv/bin/activate
pip install -e '.[test]'
pytest tests/
```

## Required environment variables

| Variable | Purpose |
|----------|---------|
| `ODOO_URL` | Base URL of the paired Odoo (e.g. `https://pbx.example.com`). The service appends `/freeswitch/firewall/api/*` paths to it. |
| `AGENT_TOKEN` | **Required.** Shared secret. Must match `connect.settings.firewall_service_token` in Odoo. Used as `Authorization: Bearer …` in both directions (this service → Odoo and Odoo → `/firewall/sync` on this service). The service exits at boot if unset. |
| `FS_ESL_HOST` | FreeSWITCH ESL host (default `127.0.0.1`). |
| `FS_ESL_PORT` | FreeSWITCH ESL port (default `8021`). |
| `FS_ESL_PASSWORD` | FreeSWITCH ESL password (default `ClueCon`). |
| `DASHBOARD_USER` | Basic auth user for the dashboard / `/firewall/sync` endpoint. |
| `DASHBOARD_PASSWORD` | Plaintext password (or set `DASHBOARD_PASSWORD_HASH` later). |

The container must run with `--network host --cap-add NET_ADMIN` so it
can manage `iptables`/`ipset` on the host kernel.

## Runtime cache

The service stores the last-known runtime config at
`/var/lib/connect-firewall/config.json` (mount a volume to persist it
across restarts). When Odoo is unreachable at boot, the service uses
this cache to bring the kernel rules up.
