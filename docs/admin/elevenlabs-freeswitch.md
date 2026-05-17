# ElevenLabs over FreeSWITCH

Bridges an inbound call routed through FreeSWITCH to an ElevenLabs Conversational
AI agent over a SIP trunk. This is the single supported transport — the SIP trunk
connects FreeSWITCH directly to ElevenLabs with no intermediate relay service.

## Prerequisites

- `connect_freeswitch` installed and a working SIP profile (see
  [FreeSWITCH Integration](freeswitch-setup.md)).
- `connect_elevenlabs` installed and synced (see
  [ElevenLabs Integration](elevenlabs-setup.md)).
- `connect_elevenlabs_freeswitch` installed (auto-installs when both
  prerequisites are present).
- An ElevenLabs plan with **SIP trunking** enabled.

## Step 1 — Provision the SIP trunk on the ElevenLabs side

In the ElevenLabs dashboard:

1. Open **Conversational AI → Agents** and pick (or create) the agent you
   want exposed over FreeSWITCH.
2. Open **Phone Numbers → Add Number → SIP Trunk**.
3. Choose **Inbound** trunk type. ElevenLabs returns:
   - SIP host (e.g. `sip.elevenlabs.io:5060`)
   - SIP username
   - SIP password
   - Optional realm / from-domain
4. Bind the trunk to the agent so an inbound INVITE with the agent's
   identifier reaches it.

> ElevenLabs identifies inbound calls by the user-part of the SIP URI
> (`sip:<agent_uid>@sip.elevenlabs.io`). Connect builds that URI from the
> `Agent ID` stored on `connect.elevenlabs_agent`.

## Step 2 — Create the FreeSWITCH gateway

In Odoo, navigate to **Connect → Configuration → FreeSWITCH → Gateways → New**.

| Field | Value |
|---|---|
| **Name** | `elevenlabs` *(must match exactly — used in dial-strings)* |
| **Proxy** | `sip.elevenlabs.io:5060` *(value from Step 1)* |
| **Username** | from Step 1 |
| **Password** | from Step 1 |
| **Register** | Off if ElevenLabs uses IP authentication, On if it requires REGISTER |
| **Realm** | from Step 1 (optional) |
| **From Domain** | from Step 1 (optional) |
| **Inbound IPs** | ElevenLabs SIP egress CIDRs if you want REGISTER-less inbound auth |

Saving the record reloads the `external` sofia profile. Verify the gateway
came up:

```
fs_cli -x "sofia status gateway elevenlabs"
```

It should show `State: REGED` (if REGISTER) or `NOREG` (if IP auth).

## Step 3 — Configure the agent

Open **Connect → ElevenLabs → Agents → \<your agent\>** and switch to the
**FreeSWITCH** tab. The FreeSWITCH tab on the agent form shows only the SIP Trunk
reference info — there is no transport selector; SIP Trunk is the only supported
transport (ADR-020).

## Step 4 — Wire the extension

Click **Extension** on the agent form to mint a `connect.exten` whose
`dst` Reference points at the agent. Pick an extension number reachable
from your dialplan (e.g. `9000`).

## Step 5 — Test

Originate an internal call to the extension:

```
fs_cli -x "originate sofia/internal/9000@<your_freeswitch_domain> &park"
```

You should see in `fs_cli`:

```
[NOTICE] mod_dialplan_xml: Processing <caller> -> 9000 in context default
[INFO] mod_dialplan_xml: matched extension elevenlabs_agent_9000
[INFO] sofia.c: Originating sofia/gateway/elevenlabs/<agent_uid>
```

Pick up an internal extension (Verto or SIP) and dial `9000`. The agent
greets you with its `first_message`.

## Transfer back to a human extension

When the agent invokes the `transfer_to_agent` system tool with a
target extension, ElevenLabs calls the agent webhook on Connect. The
bridge translates the request into an ESL `uuid_transfer` against the
inbound leg, returning the caller into your normal dialplan. Make sure
the target extension has `is_published = True` so the agent's tool sees
it as a valid target.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Bridge fails with `NORMAL_TEMPORARY_FAILURE` | Gateway down — `sofia status gateway elevenlabs` |
| 401/403 from ElevenLabs | SIP credentials wrong, or agent not bound to the trunk |
| 404 from ElevenLabs | `agent_uid` on the agent record doesn't match an EL agent — re-run **Sync Agents** |
| Call connects but no audio | Codec mismatch — confirm `output_audio_format` / `user_input_audio_format` align with what your SIP profile negotiates (`PCMU` aka `ulaw_8000` is the safe default) |
| Transfer returns "Channel … not found" | The inbound leg's UUID isn't tracked as `connect.channel.sid` — confirm `mod_xml_curl` reaches Odoo and CDR ingestion is healthy |
