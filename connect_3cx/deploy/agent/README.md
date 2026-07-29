# connect-3cx-agent

Sidecar agent bridging a 3CX V20 PBX (AI edition, 8SC+) to Oduist
Connect (`connect_3cx` deep tier, ADR-035). It holds the OAuth2 token
and the Call Control WebSocket, forwards normalized participant events
to the Odoo webhooks, polls the XAPI for finished call recordings, and
executes click-to-call requests coming back from Odoo.

## Requirements on the 3CX side

- 3CX V20, AI edition (8SC or larger) — the Call Control API and the
  Configuration API (XAPI) are gated to that tier.
- A **dedicated** API client application (Admin Console → Integrations
  → API) with both "3CX Call Control API Access" and "3CX Configuration
  API Access" checked, and the extensions to monitor enumerated on it.
  3CX keeps a single active token per client application, so nothing
  else may use this client's credentials.
- The service-principal role must allow recordings access for the
  recording poller (System Owner).

## Configuration

Only two env vars are required — everything else is pulled from Odoo
(`GET /3cx/api/config`) and cached in `/var/lib/connect-3cx/config.json`:

| Env var | Meaning |
|---|---|
| `ODOO_URL` | Base URL of the paired Odoo |
| `AGENT_TOKEN` | Shared secret = `connect.settings.threecx_api_key` |
| `PBX_URL` | (optional bootstrap) `https://pbx.example.com` |
| `CLIENT_ID` / `CLIENT_SECRET` | (optional bootstrap) 3CX API client credentials |
| `VERIFY_TLS` | set `false` for self-signed PBX certificates |
| `HTTP_BIND_HOST` / `HTTP_BIND_PORT` | agent HTTP API bind (default 0.0.0.0:8083 in Docker) |

## Run

```bash
docker run -d --name connect-3cx-agent \
  -e ODOO_URL=https://odoo.example.com \
  -e AGENT_TOKEN=<threecx_api_key> \
  -p 8083:8083 \
  -v connect-3cx-agent:/var/lib/connect-3cx \
  oduist/3cx-agent:latest
```

## Tests

```bash
pip install -e .[test]
pytest
```
