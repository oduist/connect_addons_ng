# oduist/livekit-agent

The LiveKit sidecar for `connect_livekit`. One image, two commands:

- `run` — the voice-AI agent worker (LiveKit Agents). Registered under
  the agent name `connect-livekit-agent`; dispatched explicitly by the
  number dispatch rule (inbound) or `AgentDispatchService` (outbound AI
  wizard). On dispatch it reads `agent_id` from the job metadata, pulls
  the agent config from Odoo (`/livekit/api/agent_config`, Bearer auth),
  builds an `AgentSession` with the per-agent plugin cascade
  (Deepgram/OpenAI STT, OpenAI LLM, OpenAI/ElevenLabs TTS, or OpenAI
  Realtime), runs the conversation under the time limit and posts the
  transcript back to Odoo on close.
- `upload-recordings` — watches the shared egress-out volume and PUTs
  finished files to `/livekit/webhook/recording/<name>` (Bearer auth).

## Configuration (env vars)

| Var | Purpose |
|-----|---------|
| `ODOO_URL` | Paired Odoo base URL |
| `AGENT_TOKEN` | Matches `connect.settings.livekit_agent_token` |
| `LIVEKIT_URL` / `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` | LiveKit server |
| `OPENAI_API_KEY` / `DEEPGRAM_API_KEY` / `ELEVENLABS_API_KEY` | AI fallback keys (Odoo normally supplies them per agent) |
| `EGRESS_OUT_DIR` / `STATE_DIR` | Uploader paths |

## Build & publish (multi-arch)

Per the CLAUDE.md sidecar policy: rebuilt only when a release changes
files under `deploy/agent/`; tag = short `connect_livekit` manifest
version. The worker runs on customer hardware, so build multi-arch:

```
docker buildx build --platform linux/amd64,linux/arm64 \
  --provenance=false --sbom=false \
  -t oduist/livekit-agent:<short-version> -t oduist/livekit-agent:latest \
  --push connect_livekit/deploy/agent/
```

## Tests

```
pip install -e ".[test]"
pytest
```
