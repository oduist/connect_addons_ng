# LiveKit Integration Setup

`connect_livekit` integrates a **self-hosted LiveKit stack** (WebRTC SFU +
SIP bridge + Egress recording + AI agents) with Connect. It delivers three
levels: video meetings, SIP telephony, and AI voice agents. One LiveKit
stack pairs with exactly one Odoo instance.

## Prerequisites

- A host to run the LiveKit stack (Docker + Docker Compose).
- The `livekit-api` Python package installed in the Odoo environment.
- For telephony: a BYO SIP trunk from a carrier (Telnyx, Twilio, Plivo, …).
  LiveKit is a media layer *on top of* your carrier, not a replacement.
- For AI agents: an OpenAI key (LLM), plus optionally Deepgram (STT) and
  ElevenLabs (TTS) keys.

## Deploy the stack

The compose stack and config templates live in
`connect_livekit/deploy/`. See `deploy/README.md` for the full walkthrough.

1. Generate one long random API secret and put the same key/secret into
   `livekit.yaml`, `sip.yaml` and `egress.yaml`.
2. Set the webhook URL in `livekit.yaml` to
   `https://<your-odoo>/livekit/webhook`.
3. `cp deploy/.env.example deploy/.env` and fill it in. `AGENT_TOKEN`
   comes from the Odoo settings form (below).
4. `docker compose up -d`.

Browsers require `wss://`; terminate TLS in front of port 7880 with your
existing reverse proxy and point Odoo at the TLS endpoint.

## Account Configuration

Navigate to **Connect > LiveKit > Configuration > Settings**.

| Field | Description |
|-------|-------------|
| **WS URL** | `wss://livekit.example.com` — what browsers and the worker connect to. |
| **API URL** | Optional HTTP(S) server API URL; derived from the WS URL when empty. |
| **API Key / API Secret** | Match a key from `livekit.yaml`. The secret is masked for non-managers. |
| **SIP URI** | Address of the livekit-sip service; configure it as your trunk destination at the carrier. |
| **Agent Token** | Bearer secret shared with the agent/uploader sidecar. Use **GENERATE AGENT TOKEN**, then copy it into the stack `.env`. |

On the **AI Providers** page set the Deepgram and ElevenLabs keys (the
OpenAI key from Connect general settings is reused).

Press **SYNC LIVEKIT SERVER** to verify connectivity and push the trunks,
numbers and dispatch rules.

## Level 1 — Meetings

**Connect > LiveKit > Rooms** → create a room. **Join Meeting** opens the
public page; share the copyable **Public URL** with external guests (they
authenticate purely by the unguessable link). Enable **Record Meeting** to
capture an Egress recording — it lands in **Recordings** and is transcribed
by the core OpenAI pipeline when transcription is enabled.

## Level 2 — SIP telephony

1. **Configuration > Trunks** — create a trunk. Fill **Outbound Address**
   (carrier SIP host) and, for inbound, the carrier signaling IPs in
   **Inbound Addresses**. Odoo pushes the trunk to LiveKit on save.
2. **Numbers** — add each DID, pick the trunk, and route it to a **User**,
   an **AI Agent** or a **Room**. Odoo creates the matching LiveKit
   dispatch rule.
3. **Configuration > Outgoing CallerIDs** — add the numbers the carrier
   lets you present; mark one **Default**.
4. Per user (**Connect > Users > LiveKit Phone**), enable the web phone and
   set the outgoing caller ID. Set the user's **Click-to-call Provider** to
   **LiveKit**.

At the carrier, point the trunk at the livekit-sip service (the **SIP URI**
shown in settings). Inbound DID calls ring the destination user's systray
phone; click-to-call dials out through the outbound trunk.

## Level 3 — AI voice agents

1. Build the sidecar image and run it (see `deploy/agent/README.md`):
   ```
   docker buildx build --platform linux/amd64,linux/arm64 \
     --provenance=false --sbom=false \
     -t oduist/livekit-agent:<short-version> --push \
     connect_livekit/deploy/agent/
   ```
2. **Connect > LiveKit > AI Agents** — create an agent. Choose the **Mode**
   (STT→LLM→TTS pipeline or OpenAI Realtime), the STT/LLM/TTS providers and
   models, the instructions and greeting, the time limit, and which Odoo
   tools it may call (contact / CRM / helpdesk).
3. Route an inbound number to the agent (**Numbers**, destination **AI
   Agent**), or start an outbound AI call with **Call with Agent**.

The worker pulls the agent config from Odoo at dispatch time, so edits
apply to the next call. Function-call tools reach Odoo over
`/livekit/webhook/agent/<id>/tool/<name>`, authenticated by a per-agent
token you can rotate from the agent form. Transcripts are stored as
recordings (`source = livekit-ai`) with the worker-supplied summary.
The worker reports liveness to Odoo at startup and on every dispatched
job — check **Worker Last Seen** on the LiveKit settings page to
confirm the sidecar is connected.

## Security notes

- All `connect.livekit.*` models are **admin-only**. Regular Connect users
  only get the web phone and the meeting links, through server methods.
- LiveKit webhooks are verified with the API key/secret (JWT) — keep
  **Verify LiveKit Webhooks** on in production.
- The agent token and per-agent tool tokens are secrets; regenerate them if
  exposed and update the worker environment.
- livekit-sip has **no SIP registrar** — hardphones cannot register; the web
  phone and mobile SDKs are the endpoints.
