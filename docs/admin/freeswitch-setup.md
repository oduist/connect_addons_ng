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

### Docker Compose

```yaml
services:
  freeswitch:
    build: ./connect_freeswitch/deploy
    network_mode: host
    environment:
      - ODOO_URL=http://localhost:8069
```

!!! warning "Network mode"
    FreeSWITCH requires `network_mode: host` for proper SIP/RTP port handling.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ODOO_URL` | `http://localhost:8069` | Base URL for XML cURL callbacks to Odoo. |
| `SOUND_RATES` | `8000:16000` | Supported audio sample rates. |
| `SOUND_TYPES` | `music:en-us-callie` | Prompt voices and hold music. |

### Build and Run

```bash
cd connect_freeswitch/deploy
docker compose build
docker compose up -d
```

Verify FreeSWITCH is running:

```bash
docker exec -it freeswitch fs_cli -x "status"
```

## Firewall Configuration

FreeSWITCH requires the following ports:

| Port | Protocol | Purpose |
|------|----------|---------|
| 48082 | TCP | Verto WebSocket Secure (WSS) — browser phone signaling |
| 16000-17000 | UDP | RTP media — voice audio packets |
| 65060 | UDP | SIP signaling (if using SIP phones) |
| 7443 | TCP | SIP WebSocket Secure (if using SIP over WSS) |
| 8080 | TCP | mod_xml_rpc (Odoo → FreeSWITCH commands, internal only) |

```bash
sudo ufw allow 48082/tcp
sudo ufw allow 16000:17000/udp
sudo ufw allow 65060/udp   # only if using SIP phones
```

!!! tip "RTP port range"
    The default range 16000-17000 provides 1000 ports, sufficient for up to ~500 concurrent calls. For small deployments (< 100 users), this range is more than adequate. The range is configured in `deploy/freeswitch/conf/autoload_configs/switch.conf.xml`.

## Odoo Configuration

### Settings

Navigate to **Connect > Configuration > Settings** and open the **FreeSWITCH** tab.

| Field | Description |
|-------|-------------|
| **WebSocket URL** | Verto WSS URL for the browser phone (e.g., `wss://fs.example.com:48082`). |
| **Domain** | SIP domain for FreeSWITCH registrations and routing. |
| **ICE Servers** | STUN/TURN server URIs for WebRTC (one per line). Pre-populated with public STUN servers. Customize if you use private TURN servers or need to change STUN endpoints. |

#### XML-RPC

XML-RPC settings enable Odoo to push commands to FreeSWITCH (e.g., reload gateway configuration after changes). This requires `mod_xml_rpc` to be loaded on the FreeSWITCH side.

| Field | Description |
|-------|-------------|
| **XML-RPC Host** | FreeSWITCH server hostname or IP (e.g., `fs.example.com`). |
| **XML-RPC Port** | mod_xml_rpc port (default: 8080). |
| **XML-RPC User** | mod_xml_rpc username. |
| **XML-RPC Password** | mod_xml_rpc password. |

When configured, Odoo automatically sends `sofia profile external restart reloadxml` to FreeSWITCH whenever SIP gateways are created, modified, or deleted. This ensures FreeSWITCH picks up gateway changes immediately without manual intervention.

### Endpoints

Navigate to **Connect > PBX > Endpoints** to configure user devices.

Each PBX user needs at least one endpoint to make and receive calls.

| Field | Description |
|-------|-------------|
| **Name** | Endpoint identifier. |
| **Connect User** | The PBX user this endpoint belongs to. |
| **SIP Domain** | FreeSWITCH server IP or hostname. |
| **Auth User** | SIP/Verto username (typically the extension number). |
| **Auth Password** | SIP/Verto password. |
| **SIP Enabled** | Enable SIP phone registration for this endpoint. |
| **WebRTC Enabled** | Enable browser-based Verto calling. |

### SIP Gateways

Navigate to **Connect > PBX > Gateways** to configure PSTN trunks.

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

Navigate to **Connect > PBX > Outgoing Routes** to configure call routing rules.

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

**Caller ID presented on outbound calls.** For calls leaving through a
gateway, only the **number** is sent to the PSTN — taken from the calling
user's **Outgoing CallerID** (`Connect > Users`) when configured, otherwise
the user's extension. The caller-id **name** is intentionally left blank so
the internal caller's name is never disclosed to the outside world. Internal
extension-to-extension calls are unaffected and still show the caller's
extension/name.

**Example routes:**

| Name | Pattern | Gateway | Strip | Prefix |
|------|---------|---------|-------|--------|
| International | `^\+\d{7,}$` | main-trunk | 0 | |
| Local | `^0\d{9}$` | main-trunk | 1 | +380 |
| Emergency | `^(112\|911)$` | main-trunk | 0 | |

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

To make the new code selectable from the callflow form, also override `connect.callflow._get_language_selection()` in your extension module.

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

The deploy directory includes self-signed certificates:

- `deploy/freeswitch/conf/tls/wss.pem` — for Verto WSS connections
- `deploy/freeswitch/conf/tls/dtls-srtp.pem` — for DTLS-SRTP media encryption

For production, replace these with certificates signed by a trusted CA, or use a reverse proxy (e.g., nginx) to terminate TLS.

## FreeSWITCH Configuration Files

All configuration files are in `deploy/freeswitch/conf/`. Key files:

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

Navigate to **Connect > PBX > XML Templates** to view and customize the FreeSWITCH XML configuration templates.

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

## Troubleshooting

### No audio on calls

- **Check firewall**: UDP ports 16000-17000 must be open for RTP media
- **Check STUN**: Verify `external_rtp_ip` in `vars.xml` resolves to your public IP
- **Check DTLS**: Look for "DTLS state from OFF to HANDSHAKE" in FreeSWITCH logs — if it never reaches ESTABLISHED, media ports are blocked

### Verto WebRTC not connecting

- Verify WSS port 48082 is accessible
- Check that `wss.pem` certificate is valid
- Verify the WebSocket URL in Connect settings matches the server

### FreeSWITCH can't reach Odoo

- Check the `ODOO_URL` environment variable
- Verify Odoo is accessible from the FreeSWITCH container
- Check FreeSWITCH logs: `docker exec -it freeswitch fs_cli -x "xml_curl debug_on"`

### Gateway registration failures

- Verify gateway credentials in **Connect > PBX > Gateways**
- Check SIP trunk provider firewall rules
- Review registration status: `docker exec -it freeswitch fs_cli -x "sofia status"`
