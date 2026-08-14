# Asterisk Integration

The `connect_asterisk` module connects Odoo to an **existing Asterisk
PBX** — FreePBX, Issabel or plain Asterisk (13–21). Unlike the
FreeSWITCH integration, no PBX image is shipped: your dialplan keeps
working as is, and Odoo only listens to call events and originates
click-to-call calls.

## How it works

A thin sidecar agent (`oduist/asterisk-agent` Docker image) runs next
to your Asterisk. It holds the AMI connection, forwards call events to
Odoo, uploads call recordings, and executes click-to-call requests.
Both directions authenticate with one shared secret (the *Agent
Token*) carried as an `Authorization: Bearer` header.

The web phone (JsSIP) talks SIP over WebSocket **directly to your
Asterisk** — the agent is not in the media or signaling path.

## 1. Install the module

Install `connect_asterisk` like any Odoo addon. On install a random
Agent Token is generated automatically.

## 2. Configure Connect → Asterisk → Configuration → Settings

| Setting | Meaning |
|---------|---------|
| Asterisk Enabled | Master toggle for the integration |
| Agent URL | Where Odoo reaches the agent, e.g. `http://pbx.lan:8082` |
| Agent Token | Shared secret; copy it into the agent's `AGENT_TOKEN` env var |
| AMI Host/Port/User/Password | How the agent reaches Asterisk AMI |
| Originate Context | Dialplan context for click-to-call (e.g. `from-internal`) |
| Upload Recordings | Agent uploads MixMonitor files after hangup |

## 3. Create the AMI account on the PBX

Download the rendered snippet from
`/asterisk/api/manager_conf?token=<agent token>` or copy:

```ini
[connect-agent]
secret = <AMI password from Odoo>
deny = 0.0.0.0/0.0.0.0
permit = 127.0.0.1/255.255.255.255   ; or the agent's subnet
read = call,dialplan,user
write = originate,call,reporting
```

Add it to `manager.conf` (FreePBX: a custom include) and run
`asterisk -rx "manager reload"`. The `system` and `command` write
classes are deliberately not granted.

## 4. Run the agent

```bash
docker run -d --name connect-asterisk-agent \
  -e ODOO_URL=https://odoo.example.com \
  -e AGENT_TOKEN=<agent token> \
  -e AMI_HOST=<asterisk host> \
  -e AMI_PASSWORD=<ami password> \
  -v /var/spool/asterisk/monitor:/var/spool/asterisk/monitor:ro \
  -v connect-asterisk-state:/var/lib/connect-asterisk \
  -p 8082:8082 \
  oduist/asterisk-agent:latest
```

Press **PING AGENT** in the settings form — the status fields should
show the agent version and *AMI connected*.

Topology notes:

- Agent → Odoo is outbound-only HTTPS and works behind NAT.
- Odoo → agent (click-to-call, AMI actions) requires the Agent URL to
  be reachable from Odoo (LAN, VPN or port forward). Events and
  recordings keep flowing even when it is not.
- Recording upload requires the monitor directory mounted into the
  agent container.

## 5. Map users and endpoints

For each Odoo user create a **Connect User** (**Connect > Users**) and
add an **Endpoint** under **Connect > Asterisk > Endpoints** with the *Asterisk
Channel* of their phone (e.g. `PJSIP/101`). The same `PJSIP/101` example is
shown as a placeholder when adding an endpoint inline from the Connect User
form. The endpoint matches AMI
events to the user and is dialed first on click-to-call. Optional
per-endpoint settings: originate context, auto-answer SIP header, SIP
transport. To let the dialplan route a DID to a user, map it under
**Connect > Asterisk > Numbers** (used by the `get_user_data_by_did` lookup).

If you want Odoo to manage SIP credentials, the
`/asterisk/api/sip_peers?token=...` route renders a pjsip wizard
config for all endpoints — include it from `pjsip_wizard.conf` with
`#exec curl`.

## 6. Web phone (optional)

Enable *Web Phone* in the Asterisk settings and set the WebSocket URL
(`wss://pbx.example.com:8089/ws`). Requirements on Asterisk:
`http.conf` with TLS enabled, a pjsip WebRTC transport/endpoint
(transport `webrtc` on the Odoo endpoint generates a matching
`webrtc-user` wizard peer). The browser registers with the endpoint's
SIP user/password.

## Caller name lookup from the dialplan (optional)

```
exten => _X.,n,Set(CALLERID(name)=${CURL(https://odoo.example.com/asterisk/api/get_caller_name?number=${CALLERID(num)}&token=<agent token>)})
```

Similar routes: `get_partner_manager` (route the caller to their
salesperson) and `get_user_data_by_did` (DID → user dialstring).

## Troubleshooting

- `docker logs connect-asterisk-agent` — AMI connection and event flow
  (`AMI_TRACE=true` dumps raw events).
- `asterisk -rx "manager show connected"` — the agent's AMI session.
- Connect → Asterisk → Configuration → Settings → status fields are refreshed by
  agent heartbeats every 60 s.
- Stale active calls are healed automatically: the agent reconciles
  with `CoreShowChannels` once a minute and emits synthetic hangups.
