# Dograh Integration (AI Voice Agents)

The `connect_dograh` module connects FreeSWITCH to
[Dograh](https://github.com/dograh-hq/dograh) — an open-source,
self-hostable voice-AI platform with a drag-and-drop workflow builder.
Calls to a dedicated extension are answered by a Dograh voice agent;
Dograh can also place outbound calls (campaigns, test calls) through
your FreeSWITCH trunks.

## Architecture

```
Caller ──> FreeSWITCH ──mod_audio_fork (WSS, L16/16 kHz)──> Dograh API
              ▲                                                  │
              │ XML-RPC (originate / uuid_kill)                  │
            Odoo <──────── /dograh/api/* (Bearer token) ─────────┘
```

- Odoo renders a per-call dialplan that first registers the call with
  Dograh (inbound webhook) and then streams audio to the returned
  media WebSocket via `mod_audio_fork`.
- Dograh runs the voice pipeline (STT, LLM, TTS, workflow logic) and
  calls back into Odoo to hang up or originate calls.
- The FreeSWITCH image must include `mod_audio_fork`
  (`oduist/freeswitch` 2.1.0 and later).

## 1. Deploy Dograh with the FreeSWITCH provider

Dograh does not ship a FreeSWITCH telephony provider yet. Oduist
publishes an overlay image that adds it on top of the official
release:

```
oduist/dograh-api:<dograh-version>-<module-version>   # e.g. 1.41.0-1.0.0
```

In Dograh's `docker-compose.yaml`, replace the API image:

```yaml
services:
  api:
    image: oduist/dograh-api:1.41.0-1.0.0
```

and start the stack as usual (`./scripts/start_docker.sh`). Sources
for the overlay live in `connect_dograh/deploy/` (the provider package
plus a registration script that fails the build if the Dograh base
image is incompatible).

!!! note "Network requirements"
    - **Odoo → Dograh API** over HTTP(S) (`/api/v1/telephony/inbound/run`,
      health check).
    - **FreeSWITCH → Dograh** over WSS — the media WebSocket URL is
      built from Dograh's `BACKEND_API_ENDPOINT` setting, so that URL
      must be reachable from the FreeSWITCH host.
    - **Dograh → Odoo** over HTTPS (`/dograh/api/*`).

## 2. Configure the provider in Dograh

In the Dograh UI open **Settings → Telephony** and add the
**FreeSWITCH (Oduist Connect)** provider:

| Field | Value |
|-------|-------|
| Account ID | Must equal *Dograh Account ID* in Odoo (default `odoo`) |
| Odoo URL | Your Odoo base URL, e.g. `https://odoo.example.com` |
| Service Token | Copy from Odoo (Connect → Dograh → Settings) |
| From Numbers | Optional caller IDs for outbound calls |

Then add your agent extensions on the **Phone Numbers** page and
assign each one an inbound workflow. The phone number entered in
Dograh must exactly match the FreeSWITCH extension number created in
Odoo (e.g. `9001`).

## 3. Configure Odoo

Open **Connect → Dograh → Configuration → Settings**:

- **Dograh API URL** — base URL of the Dograh API, e.g.
  `https://dograh-api.example.com`.
- **Dograh Account ID** — same value as the provider's Account ID in
  Dograh.
- **Dograh Service Token** — generated automatically; copy it into the
  provider configuration in Dograh.

Use **CHECK STATUS** to verify Odoo can reach Dograh.

## 4. Create an AI agent

1. Build and publish a workflow in Dograh.
2. In Odoo open **Connect → Dograh → AI Agents**, create an agent and
   click **Create Extension** to assign it an extension number.
3. Add the same number on Dograh's Phone Numbers page and select the
   inbound workflow.
4. Call the extension — the Dograh agent answers. Route a DID or IVR
   choice to the extension to expose it externally.

Enable **Record Calls** on the agent to record sessions through the
standard recording webhook; recordings appear on the call form and can
be transcribed/summarized by the core OpenAI integration. Dograh keeps
its own run history and transcript independently.

## Outbound calls

Dograh campaigns and test calls use the same provider: Dograh calls
`POST /dograh/api/originate`, Odoo dials the destination through the
matching **outgoing route** (Connect → FreeSWITCH → Outgoing Routes),
applies the default outgoing CallerID when Dograh does not send one,
and attaches the answered leg to the workflow's media WebSocket.

## Limitations

- Transfer-to-human from a Dograh workflow is not supported yet
  (`supports_transfers` is false); the workflow engine reports this
  gracefully if a transfer node is reached.
- The number → workflow mapping lives in Dograh, so extension numbers
  are configured in both systems (same model as Dograh's Asterisk ARI
  provider).
