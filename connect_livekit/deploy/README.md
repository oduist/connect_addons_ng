# Self-hosted LiveKit stack for connect_livekit

One stack pairs with exactly one Odoo instance (the webhook URL in
`livekit.yaml` is stack-global, ADR-036).

## Services

| Service  | Image                              | Purpose |
|----------|------------------------------------|---------|
| livekit  | `livekit/livekit-server` (pinned)  | WebRTC SFU + server API + webhooks |
| redis    | `redis:7-alpine`                   | Message bus / state for sip & egress |
| sip      | `livekit/sip` (pinned)             | SIP bridge (BYO carrier trunk) |
| egress   | `livekit/egress` (pinned)          | Recording to the shared `egress-out` volume |
| agent    | `oduist/livekit-agent`             | Voice-AI agent worker (LiveKit Agents) |
| uploader | `oduist/livekit-agent`             | Delivers egress files to Odoo |

## Setup

1. Generate a long random API secret and put the same key/secret into
   `livekit.yaml` (`keys:`), `sip.yaml` and `egress.yaml`.
2. Set the webhook URL in `livekit.yaml` to
   `https://<your-odoo>/livekit/webhook`.
3. `cp .env.example .env` and fill it in. `AGENT_TOKEN` comes from the
   Odoo LiveKit Settings form (GENERATE AGENT TOKEN).
4. `docker compose up -d`.
5. In Odoo (Connect → LiveKit → Configuration → Settings): set the WS
   URL (`wss://<public-host>` or `ws://<host>:7880`), API key/secret,
   then SYNC LIVEKIT SERVER.

## TLS

Browsers require `wss://`. Terminate TLS in front of port 7880 with your
existing proxy (Traefik/Caddy/nginx) and point `livekit_ws_url` in Odoo
at the TLS endpoint. WebRTC media flows over UDP 50000-50100 (TCP 7881
fallback) directly to the server.

## SIP trunk (carrier side)

Point the carrier trunk at this host, UDP/TCP port 5060 (`sip` service),
RTP 10000-10100/udp. Create the trunk + numbers in Odoo (Connect →
LiveKit); Odoo pushes inbound/outbound trunks and dispatch rules to
LiveKit itself. Behind NAT prefer `network_mode: host` for the sip
service and set the external IP in `sip.yaml`.

## Image versioning

`oduist/livekit-agent` is rebuilt only when a release changes files
under `deploy/agent/`; the tag equals the short `connect_livekit`
manifest version (multi-arch amd64+arm64). The upstream LiveKit images
are pinned in `docker-compose.yml` and bumped deliberately.
