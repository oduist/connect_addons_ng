# Pipecat AI Agent Setup

The Pipecat integration requires the `connect_pipecat` addon, a FreeSWITCH
image containing `mod_audio_fork`, and the `oduist/pipecat-agent:1.0.0`
sidecar. Pipecat does not run inside Odoo.

## 1. Build the images

Build the FreeSWITCH image from `connect_freeswitch/deploy` (requires
`connect_freeswitch` 19.0.2.1.0 or later). Use the image tag pinned in
`connect_freeswitch/deploy/docker-compose.yml` and
`docker-compose.full.yml` — `oduist/freeswitch:2.1.2` at the time of
writing:

```bash
docker build --platform linux/amd64 --provenance=false --sbom=false \
  -t oduist/freeswitch:2.1.2 connect_freeswitch/deploy
```

Build the sidecar:

```bash
docker build --platform linux/amd64 --provenance=false --sbom=false \
  -t oduist/pipecat-agent:1.0.0 connect_pipecat/deploy
```

`connect_pipecat/deploy/oduflow-preset.yaml` contains the service variables and
WSS routing shape.

## 2. Pair Odoo and the sidecar

Open **Connect → FreeSWITCH → Configuration → Settings → Pipecat AI**.

1. Set **Pipecat Sidecar URL** to its externally reachable base URL, for
   example `wss://voice.example.com`. Do not append `/ws`.
2. Generate a URL-safe token of at least 24 characters and enter it as the
   Pipecat service token.
3. Set exactly the same value as `PIPECAT_SERVICE_TOKEN` in the sidecar.
4. Set `ODOO_URL` in the sidecar to Odoo's HTTPS base URL.
5. Enter API keys for every provider used by an agent.
6. Restart the sidecar and click **CHECK STATUS**. A healthy service reports
   `UP (1.0.0)`.

The token authenticates both directions: FreeSWITCH uses Basic auth to open
the media WebSocket; the sidecar uses Bearer auth for Odoo and `/health`.

## 3. Configure an agent

Go to **Connect → FreeSWITCH → AI Agents**, create an agent, and configure:

- system prompt and optional greeting;
- STT, LLM and TTS providers/models;
- language, voice and maximum duration;
- optional human transfer extension;
- call recording if transcript audio should also be retained.

Use the **Extension** button to assign a unique extension number. A DID may then
route to that extension using the normal Connect routing controls.

## Verification

Call the extension and confirm the greeting is heard. Speak over a long agent
reply: playback should stop immediately (`killAudio`) and the caller's new turn
should be processed. Ask for a human and verify the configured extension rings.
After hangup, open the call in Connect and verify summary and transcript.

Check these logs when diagnosing failures:

- `mod_audio_fork::connect_failed` in FreeSWITCH: WSS, certificate or Basic
  token mismatch;
- sidecar `401`: Odoo/service token mismatch;
- provider initialization error: missing key or unsupported model/voice;
- call result `404`: CDR creation was delayed beyond the sidecar retry window.

The acceptance target is first agent audio in under 1.4 seconds with working
barge-in. Measure this in the deployment because provider and network latency
dominate the result.
