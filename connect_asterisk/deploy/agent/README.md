# connect-asterisk-agent

Thin sidecar that bridges a customer's existing Asterisk PBX (FreePBX,
Issabel, plain Asterisk 13–21) to the `connect_asterisk` Odoo module.
See `specs/decisions/025-asterisk-sidecar-agent.md` in the repo root for
the architecture decision record.

What it does — and all it does:

* holds the persistent **AMI** connection (auto-reconnect, keepalive);
* forwards a fixed allowlist of AMI events (`Newchannel`, `Newstate` Up,
  `Hangup`, `NewConnectedLine`, `OriginateResponse` Failure,
  `VarSet MIXMONITOR_FILENAME`) to Odoo's
  `/asterisk/webhook/events`, batched;
* uploads finished MixMonitor recordings to
  `/asterisk/webhook/recording/<uniqueid>.<ext>`;
* executes Odoo-initiated AMI actions (`/originate`, `/ami_action`);
* heals state gaps with periodic `CoreShowChannels` reconciliation.

No business logic, no database: direction, status mapping and user
matching all live in Odoo.

## Authentication

One shared secret — `asterisk_agent_token` in Odoo Connect Settings →
Asterisk — authenticates both directions as `Authorization: Bearer
<token>`. Copy the same value into the agent's `AGENT_TOKEN` env var.

## Environment variables

| Var | Default | Notes |
|-----|---------|-------|
| `ODOO_URL` | — required | Base URL of Odoo; the agent appends `/asterisk/...` paths |
| `AGENT_TOKEN` | — required | Shared secret = `asterisk_agent_token` in Odoo |
| `AMI_HOST` / `AMI_PORT` | `127.0.0.1` / `5038` | Bootstrap; later refreshed from Odoo `/asterisk/api/config` |
| `AMI_USER` / `AMI_PASSWORD` | `connect-agent` / — | manager.conf account |
| `AMI_PING_INTERVAL` | `30` | Keepalive ping (detects half-open TCP) |
| `HTTP_BIND_HOST` / `HTTP_BIND_PORT` | `0.0.0.0` (Docker) / `8082` | Odoo → agent API |
| `RECORDINGS_ENABLED` | `true` | Requires the monitor dir mounted |
| `RECORDING_PATHS` | `/var/spool/asterisk/monitor` | Informational; actual paths come from `MIXMONITOR_FILENAME` |
| `RECORDING_UPLOAD_DELAY` | `5` | Seconds to wait after Hangup before reading the file |
| `RECORDING_MAX_MB` | `200` | Upload size cap |
| `RECORDING_RETRY_HOURS` | `24` | Give-up horizon for failed uploads |
| `RECORDING_DELETE_AFTER_UPLOAD` | `false` | The files belong to the customer — off by default |
| `EVENT_BATCH_SIZE` / `EVENT_BATCH_WINDOW` | `50` / `0.2` | Webhook batching |
| `RECONCILE_INTERVAL` / `HEARTBEAT_INTERVAL` | `60` / `60` | Loop periods (seconds) |
| `CALL_STATE_TTL` | `21600` | In-memory channel registry TTL |
| `STATE_PATH` | `/var/lib/connect-asterisk/state.json` | Pending uploads + config cache |
| `LOG_LEVEL` / `AMI_TRACE` | `INFO` / `false` | `AMI_TRACE=true` dumps raw events at DEBUG |

## Asterisk-side configuration

Create an AMI account for the agent (Odoo renders this snippet at
`/asterisk/api/manager_conf`):

```ini
[connect-agent]
secret = <asterisk_ami_password from Odoo>
deny = 0.0.0.0/0.0.0.0
permit = 127.0.0.1/255.255.255.255   ; or the docker bridge subnet
read = call,dialplan,user
write = originate,call,reporting
```

`system` and `command` write classes are deliberately excluded: the
generic `/ami_action` passthrough is bounded by these manager.conf
permissions, which is where privilege limits belong.

No dialplan changes are required. Recordings work with however
MixMonitor is invoked (FreePBX GUI, custom dialplan) because the
filename arrives via the `VarSet MIXMONITOR_FILENAME` event.

## Topology constraints

* The agent must run **next to Asterisk** (same host or a container
  with the monitor directory mounted) for recording upload; with
  `RECORDINGS_ENABLED=false` it only needs AMI/TCP reachability.
* Agent → Odoo is outbound-only HTTP(S) and works behind NAT.
* Odoo → agent (`/originate`, `/ami_action`, `/sync`) requires the
  agent URL to be reachable from Odoo (LAN, VPN, or port forward).
  Click-to-call does not work without it; event/recording flow does.

## Run

```bash
docker run -d --name connect-asterisk-agent \
  -e ODOO_URL=https://odoo.example.com \
  -e AGENT_TOKEN=<asterisk_agent_token> \
  -e AMI_HOST=host.docker.internal \
  -e AMI_PASSWORD=<asterisk_ami_password> \
  -v /var/spool/asterisk/monitor:/var/spool/asterisk/monitor:ro \
  -v connect-asterisk-state:/var/lib/connect-asterisk \
  -p 8082:8082 \
  oduist/asterisk-agent:latest
```

## Build & publish

The image tag is the short `connect_asterisk` manifest version (strip
the leading Odoo series prefix), rebuilt only when a release changes
files under `connect_asterisk/deploy/agent/`:

```bash
docker buildx build --platform linux/amd64,linux/arm64 \
  --provenance=false --sbom=false \
  -t oduist/asterisk-agent:<short> -t oduist/asterisk-agent:latest \
  --push connect_asterisk/deploy/agent/
```

## Tests

```bash
cd connect_asterisk/deploy/agent
uv venv && uv pip install -e '.[test]'
uv run pytest
```
