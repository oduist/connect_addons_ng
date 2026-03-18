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

**Example routes:**

| Name | Pattern | Gateway | Strip | Prefix |
|------|---------|---------|-------|--------|
| International | `^\+\d{7,}$` | main-trunk | 0 | |
| Local | `^0\d{9}$` | main-trunk | 1 | +380 |
| Emergency | `^(112\|911)$` | main-trunk | 0 | |

## Text-to-Speech (Piper TTS)

The FreeSWITCH Docker image includes [Piper](https://github.com/rhasspy/piper) — a fast, local neural TTS engine — via the [mod_piper_tts](https://github.com/aks-devs/mod_piper_tts) module. No cloud TTS service is required.

### Included Voice Models

| Language | Code | Model | Voice |
|----------|------|-------|-------|
| English (US) | `en` | `en_US-lessac-medium` | Lessac |
| Russian | `ru` | `ru_RU-irina-medium` | Irina |

### Usage in Dialplan

TTS can be invoked from the XML dialplan generated by Odoo:

```xml
<action application="speak" data="piper|en|Hello, please hold while we connect your call."/>
<action application="speak" data="piper|ru|Здравствуйте, пожалуйста подождите."/>
```

### Adding Voice Models

Additional voices can be downloaded from [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices). Each voice requires two files:

- `<voice>.onnx` — the model
- `<voice>.onnx.json` — the model config

Place them in `/opt/piper/models/` inside the container and add a `<model>` entry in `autoload_configs/piper_tts.conf.xml`:

```xml
<model language="de" path="/opt/piper/models/de_DE-thorsten-medium.onnx" />
```

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
| `autoload_configs/piper_tts.conf.xml` | Piper TTS settings and voice models. |
| `sip_profiles/internal.xml` | Internal SIP profile (ports, codecs, WebSocket). |
| `dialplan/default.xml` | Fallback dialplan (echo test, hold music test). |
| `directory/default.xml` | User directory (delegates to Odoo via XML cURL). |

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
