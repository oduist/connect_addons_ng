# FreeSWITCH Integration Setup

## Architecture Overview

FreeSWITCH runs as a standalone server and queries Odoo dynamically for all routing decisions via XML cURL. This means:

- **Users, extensions, callflows, gateways, and routes** are all configured in Odoo
- **FreeSWITCH** executes the XML dialplan that Odoo generates on-the-fly
- **Verto WebRTC** provides the browser-based phone widget

```
Browser (Verto WSS) ──► FreeSWITCH ──► Odoo (XML cURL)
                             │
SIP Phone ─────────────────►│
                             │
PSTN (via SIP Gateway) ────►│
```

## Docker Deployment

The module includes a ready-to-use Docker setup in `connect_freeswitch/deploy/`.
The default `docker-compose.yml` is the production FreeSWITCH host stack
(`traefik`, `fs`, `firewall`). `docker-compose.full.yml` is a standalone
local stack that also starts Odoo 19 and PostgreSQL.

### Docker Compose

```yaml
services:
  freeswitch:
    image: oduist/freeswitch:2.1.2
    network_mode: host
    environment:
      - ODOO_URL=http://localhost:8069
      - FS_WEBHOOK_TOKEN=<value of the FreeSWITCH Webhook Token>
      - FS_DOMAIN=fs.example.com
      - FS_ESL_PASSWORD=<shared ESL password>
  firewall:
    image: oduist/freeswitch-firewall:2.1.1
    network_mode: host
    cap_add: [NET_ADMIN]
    environment:
      - ODOO_URL=http://localhost:8069
      - AGENT_TOKEN=<value of the Firewall Service Token>
      - FS_ESL_HOST=127.0.0.1
      - FS_ESL_PASSWORD=<shared ESL password>
      - HTTP_BIND_HOST=127.0.0.1
```

!!! warning "Network mode"
    FreeSWITCH requires `network_mode: host` for proper SIP/RTP port handling.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ODOO_URL` | `http://localhost:8069` | Base URL for XML cURL callbacks to Odoo. |
| `FS_WEBHOOK_TOKEN` | *(unset)* | Shared secret authenticating every FreeSWITCH → Odoo HTTP call (XML cURL, CDR, recordings, parking). **Required**: Odoo rejects the requests with 401 while it is unset or wrong. |
| `FS_DOMAIN` | *(unset)* | Public FreeSWITCH host name used for SIP/WSS domain and Traefik ACME certificate extraction. |
| `FS_ESL_PASSWORD` | `ConnectNGESLPassword` | Password for FreeSWITCH ESL. Set the same value on `fs` and `firewall`. |
| `FIREWALL_AGENT_TOKEN` | *(unset)* | Shared secret for Odoo ↔ firewall service calls. Must match Firewall Service Token in Odoo settings. |
| `FIREWALL_DASHBOARD_PASSWORD` | *(unset)* | Basic-auth password for the firewall dashboard. |
| `SOUND_RATES` | `8000:16000` | Supported audio sample rates. |
| `SOUND_TYPES` | `music:en-us-callie` | Prompt voices and hold music. |

### Webhook Token Pairing

Odoo authenticates all incoming FreeSWITCH HTTP requests with a shared
secret. A random token is generated automatically on install/upgrade,
which **locks the endpoints until you pair the container**:

1. Install or upgrade `connect_freeswitch`. The missing-only deployment
   bootstrap creates both this token and the firewall service token without
   changing existing values.
2. Let Oduflow read `connect.settings.freeswitch_webhook_token` through a
   sudo Odoo shell and pass it directly to the `fs` service as
   `FS_WEBHOOK_TOKEN`. Treat the shell output as a secret and do not store it
   in the repository or repeat it in deployment reports.
3. For a manual deployment, retrieve the same protected setting with an Odoo
   shell and put it in the container environment. Entering a new value in the
   **FreeSWITCH Webhook Token** field is an explicit rotation, not a normal
   installation step.
4. Restart or recreate the `fs` container after setting the environment
   variable.

Without the pairing, registrations, dialplan lookups, CDRs and
recording uploads all fail with HTTP 401 (fail-closed by design).

The Oduflow agent procedure for retrieving both generated tokens and updating
services without losing their existing environment is defined in
`AGENTS.md`, section **Deploying the `fs` and `firewall` services with
Oduflow**.

### Build and Run

```bash
cd connect_freeswitch/deploy
docker compose up -d
```

For the local all-in-one stack:

```bash
docker compose -f docker-compose.full.yml up -d
```

Verify FreeSWITCH is running:

```bash
docker exec freeswitch sh -c 'fs_cli -p "$FS_ESL_PASSWORD" -x "status"'
```

## Firewall Configuration

FreeSWITCH requires the following ports:

| Port | Protocol | Purpose |
|------|----------|---------|
| 48082 | TCP | Verto WebSocket Secure (WSS) — browser phone signaling |
| 16000-17000 | UDP | RTP media — voice audio packets |
| 5080 | UDP+TCP | SIP signaling (sofia `external` profile) — trunks and SIP phones |
| 443 | TCP | XML-RPC over HTTPS (Odoo → Traefik → FreeSWITCH commands) |
| 8080 | TCP | mod_xml_rpc plain HTTP — **internal only**, never expose; Traefik proxies to it |
| 8081 | TCP | firewall service plain HTTP — **internal only**, bound to loopback; Traefik proxies `/firewall` to it |

```bash
sudo ufw allow 48082/tcp
sudo ufw allow 16000:17000/udp
sudo ufw allow 5080/udp
sudo ufw allow 5080/tcp
```

!!! tip "RTP port range"
    The default range 16000-17000 provides 1000 ports, sufficient for up to ~500 concurrent calls. For small deployments (< 100 users), this range is more than adequate. The range is configured in `deploy/freeswitch/conf/autoload_configs/switch.conf.xml`.

## Odoo Configuration

### Settings

Navigate to **Connect > FreeSWITCH > Configuration > Settings**.

| Field | Description |
|-------|-------------|
| **WebSocket URL** | Verto WSS URL for the browser phone (e.g., `wss://fs.example.com:48082`). |
| **Domain** | SIP domain for FreeSWITCH registrations and routing. |
| **ICE Servers** | STUN/TURN server URIs for WebRTC (one per line). Pre-populated with public STUN servers. Customize if you use private TURN servers or need to change STUN endpoints. |

#### XML-RPC

XML-RPC settings enable Odoo to push commands to FreeSWITCH (e.g., reload gateway configuration after changes). This requires `mod_xml_rpc` to be loaded on the FreeSWITCH side.

Odoo always connects to XML-RPC **over HTTPS**. `mod_xml_rpc` has no native TLS, so Traefik terminates HTTPS in front of it and proxies to the internal plain-HTTP port (`8080`). This keeps the HTTP Basic Auth credential off the wire in cleartext — without it, anyone able to observe the network path between Odoo and FreeSWITCH could capture a credential that grants full control of the switch (originate, eavesdrop, eval). The reverse proxy is wired in `deploy/docker-compose.yml` (the `traefik` service plus `deploy/traefik/`).

| Field | Description |
|-------|-------------|
| **XML-RPC Host** | Public DNS host of the Traefik TLS endpoint that fronts FreeSWITCH (e.g., `fs.example.com`). Enter a hostname only, without `https://`, a port, or a path. |

Odoo always connects to verified HTTPS on port `443`. The XML-RPC username is
fixed to `odoo`, and the password is generated and stored internally. Changing
the host rotates the password; restart the FreeSWITCH container afterwards so
`mod_xml_rpc` fetches the new credential from Odoo.

Upgrading to the managed XML-RPC configuration also rotates the legacy
operator-managed password once. Restart FreeSWITCH immediately after the
module upgrade.

The pinned FreeSWITCH image restricts the plain-HTTP backend to
`127.0.0.1:8080`. Traefik shares the host network namespace and is the only
public route to it.

When configured, Odoo automatically sends `sofia profile external restart reloadxml` to FreeSWITCH whenever SIP gateways are created, modified, or deleted. This ensures FreeSWITCH picks up gateway changes immediately without manual intervention.

#### Checking server status

The **CHECK STATUS** button on the FreeSWITCH settings form probes the
server over XML-RPC and writes the result to the **Server Status**
field. When the probe fails, the field shows the specific reason so you
know which side to fix:

| Server Status | Meaning | What to do |
|---------------|---------|------------|
| `UP — <version>` | FreeSWITCH reachable and answering. | Nothing — healthy. |
| `NOT CONFIGURED` | No XML-RPC host set in Odoo; no connection is attempted. | Fill in the XML-RPC Host above. |
| `UNREACHABLE` | Host set but the verified TLS connection to port `443` failed (firewall, DNS, routing, or an invalid/untrusted certificate). | Check the host, Traefik, DNS, port `443`, and the public certificate. |
| `AUTH FAILED` | Host reachable but `mod_xml_rpc` rejected the internally managed credential (HTTP 401). | Restart FreeSWITCH so it fetches the current generated credential from Odoo; check Odoo/FreeSWITCH XML-curl connectivity if it persists. |
| `INVALID RESPONSE` | Server answered but the payload could not be parsed. | Check the FreeSWITCH logs and the `mod_xml_rpc` configuration. |

### Endpoints

Navigate to **Connect > FreeSWITCH > Endpoints** to configure user devices.

Each PBX user needs at least one endpoint to make and receive calls.

| Field | Description |
|-------|-------------|
| **Name** | Endpoint identifier. |
| **Connect User** | The PBX user this endpoint belongs to. |
| **SIP Domain** | FreeSWITCH server IP or hostname. |
| **Auth User** | SIP/Verto username (typically the extension number). |
| **Auth Password** | SIP/Verto password. **Auto-generated** on creation as a typeable passphrase (e.g. `flour3-tower9-rome1-watching2-hello8`) and read-only. Masked by default — use the eye toggle to reveal it for manual entry on a device, the clipboard button to copy it, or **Regenerate** to issue a new one. |
| **SIP Enabled** | Enable SIP phone registration for this endpoint. |
| **WebRTC Enabled** | Enable browser-based Verto calling. |

### SIP Gateways

Navigate to **Connect > FreeSWITCH > Configuration > SIP Gateways** to configure PSTN trunks.

A gateway connects FreeSWITCH to an external SIP provider for making/receiving calls to/from the public phone network.

| Field | Description |
|-------|-------------|
| **Name** | Unique gateway identifier (e.g., `provider-trunk`). |
| **Proxy** | SIP proxy address of the trunk provider (e.g., `sip.provider.com`). |
| **Username** | Trunk authentication username. |
| **Password** | Trunk authentication password. |
| **Realm** | SIP realm (optional, defaults to proxy). |
| **From Domain** | Custom From header domain (optional). |
| **Register** | Enable SIP registration with the provider. |
| **Caller ID in From** | Include caller ID number in the SIP From header. |
| **Expire Seconds** | Registration expiry (default: 3600). |
| **Retry Seconds** | Registration retry interval (default: 30). |
| **Inbound IPs** | IP addresses or CIDR ranges (one per line) allowed to send inbound calls without SIP authentication. Use this when your provider sends INVITEs without credentials and expects IP-based trust. |

### Outgoing Routes

Navigate to **Connect > FreeSWITCH > Configuration > Outgoing Routes** to configure call routing rules.

Routes determine how outbound calls are sent through SIP gateways.

| Field | Description |
|-------|-------------|
| **Name** | Route description (e.g., "International calls"). |
| **Pattern** | Regex pattern to match dialed numbers (e.g., `^\+\d{7,}$`). |
| **Gateway** | Which SIP gateway to use for matched calls. |
| **Priority** | Evaluation order (lower = higher priority). |
| **Strip** | Number of leading digits to remove before sending to gateway. |
| **Prefix** | Digits to prepend after stripping. |

Routes are evaluated in priority order; the first matching pattern is used.

**Example routes:**

| Name | Pattern | Gateway | Strip | Prefix |
|------|---------|---------|-------|--------|
| International | `^\+\d{7,}$` | main-trunk | 0 | |
| Local | `^0\d{9}$` | main-trunk | 1 | +380 |
| Emergency | `^(112\|911)$` | main-trunk | 0 | |

### Outbound Caller ID (DID)

The number the called party sees on an outbound PSTN call is resolved in
this order:

1. The caller's **Outgoing Caller ID** (per-user, set on the Connect User
   form).
2. The **system-wide default** Caller ID — the entry under
   **Connect > FreeSWITCH > Outgoing Caller IDs** flagged **Default** — used when the user
   has no per-user number assigned.
3. The user's **extension number**, when neither of the above is configured.

Only the **number** is sent to the PSTN — the caller-id **name** is
intentionally left blank so the internal caller's name is never disclosed to
the outside world.

This applies to both click-to-call from Odoo and calls dialed directly from
a registered desk phone or the WebRTC (Verto) softphone. Internal
extension-to-extension calls are unaffected — they always present the
extension number and the caller's name.

> The legacy gateway-level **Caller ID in From** toggle only controls
> whether the resolved number is copied into the SIP `From:` header; it does
> not select the number itself.

## Text-to-Speech (Piper TTS)

The FreeSWITCH Docker image includes [Piper](https://github.com/rhasspy/piper) — a fast, local neural TTS engine — via the [mod_piper_tts](https://github.com/aks-devs/mod_piper_tts) module. No cloud TTS service is required.

### Included Voice Models

Callflows pick a language from a fixed list (see **Callflow → Language**). Each entry corresponds to one bundled Piper voice model. Codes are BCP-47, identical to those used by Twilio Say (Polly).

| Language | Code | Piper voice |
|----------|------|-------------|
| Catalan (Spain) | `ca-ES` | `ca_ES-upc_ona-medium` |
| Czech | `cs-CZ` | `cs_CZ-jirka-medium` |
| Danish | `da-DK` | `da_DK-talesyntese-medium` |
| German | `de-DE` | `de_DE-thorsten-medium` |
| English (UK) | `en-GB` | `en_GB-alba-medium` |
| English (US) | `en-US` | `en_US-lessac-medium` |
| Spanish (Spain) | `es-ES` | `es_ES-davefx-medium` |
| Spanish (Mexico) | `es-MX` | `es_MX-claude-high` |
| Finnish | `fi-FI` | `fi_FI-harri-medium` |
| French | `fr-FR` | `fr_FR-siwis-medium` |
| Hungarian | `hu-HU` | `hu_HU-anna-medium` |
| Icelandic | `is-IS` | `is_IS-salka-medium` |
| Italian | `it-IT` | `it_IT-paola-medium` |
| Dutch (Belgium) | `nl-BE` | `nl_BE-nathalie-medium` |
| Dutch (Netherlands) | `nl-NL` | `nl_NL-mls-medium` |
| Polish | `pl-PL` | `pl_PL-gosia-medium` |
| Portuguese (Brazil) | `pt-BR` | `pt_BR-faber-medium` |
| Portuguese (Portugal) | `pt-PT` | `pt_PT-tugao-medium` |
| Romanian | `ro-RO` | `ro_RO-mihai-medium` |
| Russian | `ru-RU` | `ru_RU-irina-medium` |
| Slovak | `sk-SK` | `sk_SK-lili-medium` |
| Swedish | `sv-SE` | `sv_SE-nst-medium` |
| Turkish | `tr-TR` | `tr_TR-dfki-medium` |
| Ukrainian | `uk-UA` | `uk_UA-ukrainian_tts-medium` |
| Vietnamese | `vi-VN` | `vi_VN-vais1000-medium` |
| Chinese (Mandarin) | `zh-CN` | `zh_CN-huayan-medium` |

### Usage in Dialplan

TTS is invoked from the XML dialplan generated by Odoo. The language token is the full BCP-47 code (e.g. `pt-BR` and `pt-PT` resolve to different voices):

```xml
<action application="speak" data="piper|en-US|Hello, please hold while we connect your call."/>
<action application="speak" data="piper|ru-RU|Здравствуйте, пожалуйста подождите."/>
```

### Adding Voice Models

Additional voices can be downloaded from [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices). Each voice requires two files:

- `<voice>.onnx` — the model
- `<voice>.onnx.json` — the model config

Place them in `/opt/piper/models/` inside the container and add a `<model>` entry in `autoload_configs/piper_tts.conf.xml`:

```xml
<model language="de-AT" path="/opt/piper/models/de_AT-some-voice-medium.onnx" />
```

To make the new code selectable from the callflow form, also override `connect.freeswitch.callflow._get_language_selection()` in your extension module.

### Configuration

TTS settings are in `autoload_configs/piper_tts.conf.xml`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `cache-path` | `/tmp/piper-tts-cache` | Directory for cached synthesized audio |
| `cache-enable` | `true` | Cache synthesized audio (MD5-based dedup) |
| `piper-bin` | `/opt/piper/piper` | Path to the Piper binary |
| `piper-opts` | (empty) | Extra CLI options for Piper |
| `voice-name-as-language` | `true` | Use voice name field as language code |

## TLS/SSL Certificates

FreeSWITCH is always deployed behind **Traefik**, which is the single TLS edge for the stack (`deploy/docker-compose.yml` → `traefik` service, config in `deploy/traefik/`):

- **Verto WSS / DTLS-SRTP** — FreeSWITCH terminates these itself. The `oduist/freeswitch` entrypoint extracts the freshest certificate from Traefik's ACME store (`acme.json`, shared via the `traefik-acme` volume) into `tls/wss.pem` and `tls/dtls-srtp.pem`. With no ACME cert available (local development) it falls back to a self-signed certificate.
- **XML-RPC** — `mod_xml_rpc` has no native TLS, so Traefik terminates HTTPS in front of it (`deploy/traefik/dynamic.yml`) and proxies to the internal `127.0.0.1:8080` port. The same certificate Traefik manages secures this control-plane channel; Odoo connects over `https://`.
- **Firewall dashboard/API** — Traefik routes `/firewall` to the firewall service on `127.0.0.1:8081`; the service itself remains loopback-only.

Traefik requests a **Let's Encrypt** certificate out of the box. Set
`FS_DOMAIN` (the public FQDN of the FreeSWITCH host) and `ACME_EMAIL` in
`deploy/.env`; while testing the edge itself, point `ACME_CASERVER` at the
Let's Encrypt staging URL to avoid rate limits. Odoo deliberately rejects the
staging and self-signed certificates because XML-RPC certificate verification
is always enabled. Switch to the production CA before testing Odoo →
FreeSWITCH commands.

## FreeSWITCH Configuration Files

Static bootstrap sources are in `deploy/freeswitch/conf/` and are copied into
the `oduist/freeswitch` image at build time. Do not mount that source directory
over the container configuration in production: Odoo returns dynamic PBX data
through `mod_xml_curl`, while these files are the versioned bootstrap that
loads the integration modules and binds internal services securely. Key files:

| File | Purpose |
|------|---------|
| `vars.xml` | Global variables (domain, codecs, STUN servers). |
| `autoload_configs/verto.conf.xml` | Verto WebRTC settings (WSS binding, codecs, ICE). |
| `autoload_configs/sofia.conf.xml` | SIP protocol (loads SIP profiles). |
| `autoload_configs/xml_curl.conf.xml` | XML cURL bindings to Odoo. |
| `autoload_configs/xml_cdr.conf.xml` | CDR webhook to Odoo. |
| `autoload_configs/switch.conf.xml` | Core settings (max sessions, RTP port range). |
| `autoload_configs/modules.conf.xml` | Loaded FreeSWITCH modules. |
| `autoload_configs/http_cache.conf.xml` | HTTP file interface for recording uploads. |
| `autoload_configs/piper_tts.conf.xml` | Piper TTS settings and voice models. |
| `sip_profiles/internal.xml` | Internal SIP profile (ports, codecs, WebSocket). |
| `dialplan/default.xml` | Fallback dialplan (echo test, hold music test). |
| `directory/default.xml` | User directory (delegates to Odoo via XML cURL). |

## XML Templates

Navigate to **Connect > FreeSWITCH > Configuration > XML Templates** to view and customize the FreeSWITCH XML configuration templates.

Odoo generates FreeSWITCH XML dynamically using Jinja2 templates. Each template produces a specific piece of configuration — user directory entries, dialplan extensions, gateway definitions, etc. The system ships with sensible defaults, but administrators can customize any template to modify the generated XML.

### Template List

| Template | Section | Description |
|----------|---------|-------------|
| `directory_user` | Directory | Single user authentication entry |
| `directory_full` | Directory | Full directory with all endpoints |
| `dialplan_user_bridge` | Dialplan | Bridge call to user endpoints |
| `dialplan_ivr` | Dialplan | IVR with digit collection and choices |
| `dialplan_ring_group` | Dialplan | Ring group bridging to multiple users |
| `dialplan_inbound_did` | Dialplan | Inbound DID routing |
| `dialplan_outgoing_route` | Dialplan | Outbound call routing via gateway |
| `dialplan_system` | Dialplan | System extensions (echo test) |
| `config_sofia` | Configuration | Sofia SIP profile with gateways |
| `config_sofia_gateway` | Configuration | Single SIP gateway element |
| `config_acl` | Configuration | ACL for gateway IP whitelisting |
| `config_xml_rpc` | Configuration | XML-RPC server settings |

### Customizing Templates

Each template form shows:

- **Available Variables** — Documents the Jinja2 variables available for rendering
- **Template** tab — The editable Jinja2 template (XML with `{{ variable }}` placeholders)
- **Default Template** tab — The factory default for reference

Templates use standard [Jinja2 syntax](https://jinja.palletsprojects.com/): `{{ variable }}` for values, `{% if %}` for conditionals, `{% for %}` for loops.

### Reset to Default

If a customized template causes issues, click **Reset to Default** in the form header to restore the factory default. Templates with customizations are marked with the **Customized** flag in the list view.

## XML cURL Integration

FreeSWITCH fetches dynamic configuration from Odoo via HTTP:

| Endpoint | Purpose |
|----------|---------|
| `POST /freeswitch/xml` (directory binding) | User authentication and registration. Returns user credentials, dial-strings, and Verto parameters. |
| `POST /freeswitch/xml` (dialplan binding) | Call routing. Odoo generates XML extensions based on DIDs, extensions, callflows, and outgoing routes. |
| `POST /freeswitch/xml` (configuration binding) | Sofia gateway configuration. Returns active SIP gateways. |
| `POST /freeswitch/webhook/cdr` | Call detail records. FreeSWITCH sends CDR XML after each call. |
| `PUT /freeswitch/webhook/recording/<uuid>.wav` | Call recordings. FreeSWITCH uploads recorded audio files. |

## Testing

### Echo Test

Dial **9196** from a registered Verto or SIP phone. The echo test answers the call and plays back everything you say. This verifies:

- Signaling (WebSocket/SIP) is working
- Media (RTP/DTLS) is flowing in both directions
- Codecs are negotiating correctly

If you hear silence, check that UDP ports 16000-17000 are open in your firewall.

### Hold Music Test

Dial **9664** to hear hold music. This tests one-way audio from FreeSWITCH to the client.

## NAT Handling

The sofia profile includes automatic NAT detection and contact rewriting for SIP phones behind NAT. When a phone registers from a private network, FreeSWITCH detects the NAT and rewrites the registration contact to use the phone's public IP and port. This ensures inbound calls reach the phone correctly.

The following profile-level parameters handle NAT transparently:

| Parameter | Purpose |
|-----------|---------|
| `aggressive-nat-detection` | Detects NAT by comparing Via header IP with actual packet source IP |
| `NDLB-received-in-nat-reg-contact` | Rewrites stored Contact with the received public IP:port |
| `nat-options-ping` | Sends periodic SIP OPTIONS to keep NAT pinholes open |
| `apply-nat-acl` | Applies NAT handling for RFC 1918 private IP ranges |

No per-user configuration is needed — NAT handling applies automatically to all registrations on the external profile.

## Operations Runbook

### Rotate the SIP trunk password

Use this procedure when the SIP provider forces a credential rotation or
as routine security hygiene. The mechanics are simple: saving a new
password on the gateway record automatically restarts the sofia
`external` profile, FreeSWITCH re-reads the gateway XML through
xml_curl and re-registers within a few seconds.

**Coordination.** If the provider portal requires setting the new
password manually, agree on the order with the provider first: set the
new password on the provider side, then in Odoo. Between the two steps
outbound registration fails with `FAIL_WAIT`, so keep the window short.
The expected registration gap after the Odoo save is a few seconds.

**Steps:**

1. Obtain (or generate and set) the new trunk password in the
   provider's portal.
2. In Odoo open **Connect → FreeSWITCH → Gateways**, open the trunk
   gateway and paste the new value into **Password** (the field is
   visible to Connect admins only), then **Save**. The save schedules a
   post-commit `sofia profile external restart reloadxml`, so the new
   credentials are picked up without touching the container.

   The same change over the API (e.g. from an Odoo shell):

   ```python
   env['connect.freeswitch.gateway'].search(
       [('name', '=', 'mytrunk')]).write({'password': 'NEW-SECRET'})
   ```

**Verification:**

1. Check the registration state — `State` must be `REGED`:

   ```
   fs_cli -x "sofia status gateway mytrunk"
   ```

2. Smoke test: one outbound call through the trunk and one inbound call
   to a DID.

**Recovery (wrong password):**

- `sofia status gateway <name>` shows `FAIL_WAIT` / `TRYING` instead of
  `REGED` and the provider rejects REGISTER with 401/403. Revert by
  writing the previous password back on the gateway record (same flow,
  the profile restarts again).
- If the profile looks stuck, force the reload manually:

  ```
  fs_cli -x "sofia profile external restart reloadxml"
  ```

## Troubleshooting

### Incoming calls not reaching SIP phone

If a SIP phone can make outgoing calls but does not ring for incoming calls:

1. Check the registration contact address:
    ```bash
    fs_cli -x "sofia status profile external reg"
    ```
    The contact should show the phone's **public** IP, not a private IP (10.x, 172.16-31.x, 192.168.x).

2. If the contact shows a private IP, verify the NAT parameters are present in the sofia profile configuration (see [NAT Handling](#nat-handling) above).

3. After upgrading the module, restart the sofia profile:
    ```bash
    fs_cli -x "sofia profile external restart reloadxml"
    ```

### Inbound call dropped with 404 (DID format mismatch)

Inbound DID matching tolerates an optional leading `+`: a number stored as
`+41215121140` matches a trunk that delivers `41215121140`, and vice-versa.
You do **not** need to match the trunk's exact E.164/national format when
entering the DID under **Connect > FreeSWITCH > Numbers**.

If an inbound call still drops with a 404, the delivered digits themselves do
not match. Check the `destination_number` the trunk actually sends (Odoo debug
log, or `fs_cli` console at debug level) and make sure the stored DID's digits
match it — differences beyond a leading `+` (e.g. an extra national prefix) are
not normalized and require the stored number to match the delivered digits.

## Troubleshooting

### No audio on calls

- **Check firewall**: UDP ports 16000-17000 must be open for RTP media
- **Check STUN**: Verify `external_rtp_ip` in `vars.xml` resolves to your public IP
- **Check DTLS**: Look for "DTLS state from OFF to HANDSHAKE" in FreeSWITCH logs — if it never reaches ESTABLISHED, media ports are blocked

### Verto WebRTC not connecting

- Verify WSS port 48082 is accessible
- Check that `wss.pem` certificate is valid
- Verify the WebSocket URL in the FreeSWITCH settings matches the server

### FreeSWITCH can't reach Odoo

- Check the `ODOO_URL` environment variable
- Verify Odoo is accessible from the FreeSWITCH container
- Check FreeSWITCH logs: `docker exec -it freeswitch fs_cli -x "xml_curl debug_on"`

### Gateway registration failures

- Verify gateway credentials in **Connect > FreeSWITCH > Configuration > SIP Gateways**
- Check SIP trunk provider firewall rules
- Review registration status: `docker exec -it freeswitch fs_cli -x "sofia status"`
