# Webhooks & Security

ElevenLabs talks to Odoo over HTTP webhooks in two directions:

- **Per-call and post-call webhooks** that ElevenLabs calls to fetch context and
  deliver results.
- **Server-tool webhooks** that the agent calls mid-conversation to act inside
  Odoo (transfer, create partner, calendar).

## Public URL requirement

Your Odoo instance **must be reachable from the internet over HTTPS**. Set the
core **API URL** (**Connect ▸ Configuration ▸ Settings**) to that public URL.
The module builds the initiation and post-call webhook URLs from it and pushes
them into your ElevenLabs workspace settings; each server tool's URL is also
built from it.

## Webhook routes

All routes are declared `type='http'`, `auth='public'`, `csrf=False` and live
under `/connect_elevenlabs/`.

| Route | Auth | Purpose |
|-------|------|---------|
| `POST /connect_elevenlabs/conversation_initiation` | agent token | ElevenLabs fetches per-call dynamic variables before opening the conversation (partner, history, users directory, published extensions). |
| `POST /connect_elevenlabs/post_call` | HMAC signature | ElevenLabs posts conversation metadata after the call; logs a `connect.call` + `connect.recording`. |
| `POST /connect_elevenlabs/transfer` | agent token | Agent tool: transfer the live call to a published extension. |
| `POST /connect_elevenlabs/create_partner` | agent token | Agent tool: create a `res.partner` for the caller and link it to the call. |
| `POST /connect_elevenlabs/get_available_slots` | agent token | Calendar tool: free business-hours slots. |
| `POST /connect_elevenlabs/create_event` | agent token | Calendar tool: book an event. |
| `POST /connect_elevenlabs/get_current_date` | agent token | Calendar tool: current server date/time. |
| `POST /connect_elevenlabs/get_meetings` | agent token | Calendar tool: list a partner's meetings. |
| `POST /connect_elevenlabs/remove_meeting` | agent token | Calendar tool: cancel a meeting. |

## Authentication

The module uses **two different mechanisms**, because ElevenLabs authenticates
its two workspace webhooks differently.

### Agent token (`x-elevenlabs-agent-token`)

The conversation-initiation webhook and **every server tool** are guarded by a
shared secret token. ElevenLabs sends it back as the `x-elevenlabs-agent-token`
request header on each call; the controller compares it (via `check_tool_token`)
against the `elevenlabs_agent_token` setting and returns **401 Unauthorized** on
mismatch or when the header/setting is missing.

The token is generated on install and **rotated on every SYNC**
(`elevenlabs_reset_token`), which then re-pushes it to the ElevenLabs workspace
settings and to every server tool so they stay in step. Rotate it by running
**SYNC** on the settings form.

### HMAC signature (post-call webhook)

ElevenLabs authenticates the **post-call** webhook by HMAC signature only (there
is no custom header for it), so the module creates the workspace webhook entity
itself, stores the returned secret, and selects it for `transcript` post-call
delivery. The controller verifies the `ElevenLabs-Signature` header on every
delivery:

- Header format `t=<unix_ts>,v0=<hex_hmac_sha256>`; the signed message is
  `"<t>.<raw_body>"` and the key is the stored webhook secret.
- Deliveries whose signed timestamp is more than **30 minutes** old are rejected
  (anti-replay).
- A missing secret, missing/short header, out-of-tolerance timestamp, or HMAC
  mismatch all return **401 Unauthorized**.

!!! danger "Keep the post-call secret in sync"
    The webhook secret is stored on `connect.settings`
    (`elevenlabs_post_call_webhook_secret`, manager-only, read-only in the UI)
    when the webhook entity is created. If it is missing, post-call verification
    fails with *"no webhook secret configured; run ElevenLabs sync"* — run
    **SYNC** to (re)create the webhook and store its secret. The secret is
    rotated automatically if the API URL drifts.

### Resilience

- The conversation-initiation controller always returns a valid JSON envelope;
  any internal error becomes an empty-variables response so ElevenLabs does not
  drop the call.
- The post-call controller returns an empty **200** on any internal processing
  error so ElevenLabs does not retry, and dedupes by `conversation_id` so
  re-delivery is safe.

## Security groups & access

The module reuses the core Connect groups:

- **Connect User** (`connect.group_user`) — read access to the ElevenLabs config
  models (except agent templates).
- **Connect Administrator** (`connect.group_admin`) — full CRUD; required for the
  Configuration menu, agent templates, and agent/tool editing.
- **Connect Webhook** (`connect.group_webhook`) — the identity server-tool
  controllers run as (the transfer controller runs the agent as the
  `connect.user_connect_webhook` user).
- **Public** (`base.group_public`) — read on `connect.elevenlabs_file` so Twilio
  can `<Play>` the generated TTS audio.

Model access (`security/*.xml`):

| Model | User | Admin | Webhook | Public |
|-------|------|-------|---------|--------|
| `connect.elevenlabs_agent` | Read | Full | Read | — |
| `connect.elevenlabs_agent_tool` | Read | Full | Read | — |
| `connect.agent_tool_params` | Read | Full | Read | — |
| `connect.elevenlabs_agent_prompt` | Read | Full | — | — |
| `connect.elevenlabs_agent_transfer` | Read | Full | — | — |
| `connect.elevenlabs_agent_template` | — | Full | — | — |
| `connect.elevenlabs_voice` | Read | Read + Create + Unlink | — | — |
| `connect.elevenlabs_file` | Read | Full | — | Read |

!!! note "Voice model is read-only for admins too"
    Admins can create/delete voices (the sync does) but not `write` them —
    voices are imported from ElevenLabs and their fields are read-only.

The **API Key**, **agent token**, and **post-call webhook id/secret** are
protected at the field level (`base.group_erp_manager` only) and masked (`****`)
for non-managers; they are never returned to the public webhook identity.
