# FreeSWITCH Docker Image

FreeSWITCH built from source (`v1.10.12`) with only the modules needed for Odoo integration.

Includes [mod_piper_tts](https://github.com/aks-devs/mod_piper_tts) for local neural text-to-speech via [Piper](https://github.com/rhasspy/piper) with English and Russian voice models.

## What's Inside

Built from source with a minimal module set:

| Category | Modules |
|----------|---------|
| Loggers | mod_logfile |
| XML Interfaces | mod_xml_curl, mod_xml_cdr, mod_xml_rpc |
| Event Handlers | mod_event_socket |
| Endpoints | mod_sofia, mod_loopback, mod_rtc, mod_verto |
| Applications | mod_commands, mod_curl, mod_dptools, mod_http_cache, mod_dialplan_xml |
| Codecs | mod_opus, mod_spandsp |
| File Formats | mod_sndfile, mod_native_file, mod_tone_stream |
| TTS | mod_piper_tts |

To add a module: edit `modules.conf` in the Dockerfile, add config in `freeswitch/conf/autoload_configs/`, rebuild.

## Configuration ownership

The image contains the complete static bootstrap configuration needed to load
FreeSWITCH, map environment variables, contact Odoo through `mod_xml_curl`, and
bind SIP/Verto/ESL. Odoo remains the source of truth for dynamic users,
extensions, gateways, ACLs, and dialplan entries.

Do not bind mount a host directory over
`/usr/local/freeswitch/etc/freeswitch` in production. Such a mount replaces
the versioned bootstrap and can silently disable the Odoo modules or expose
ESL. Build a derived image if a deployment genuinely needs static overrides.

The image applies a narrow patch to the pinned FreeSWITCH `mod_xml_rpc`
source, restricting its plain-HTTP management listener to
`127.0.0.1:8080`. Upstream `mod_xml_rpc` exposes only a port setting and
otherwise binds every interface. Traefik shares the host network namespace and
is the only public XML-RPC route.

The exact bootstrap boundary, the carried FreeSWITCH source patch, and its
upgrade verification checklist are documented in
[`freeswitch/README.md`](freeswitch/README.md).

## Building the Image

```bash
cd connect_freeswitch/deploy
docker build --platform linux/amd64 -t oduist/freeswitch:2.1.1 -t oduist/freeswitch:latest .
```

## Running the Container

```bash
docker run -d \
  --name freeswitch \
  --net host \
  -e ODOO_URL=http://localhost:8069 \
  oduist/freeswitch:latest
```

## Checking Status

```bash
docker logs freeswitch
docker exec freeswitch sh -c 'fs_cli -p "$FS_ESL_PASSWORD" -x "status"'
```

## Publishing the Image

```bash
docker push oduist/freeswitch:2.1.1
docker push oduist/freeswitch:latest
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ODOO_URL` | `http://localhost:8069` | URL of Odoo server for webhooks |
| `FS_WEBHOOK_TOKEN` | — | Odoo-generated shared secret for XML-curl, CDR, recording, and parking callbacks. Read `freeswitch_webhook_token` from Odoo and pass it unchanged; do not invent a second value. |
| `SOUND_RATES` | `8000:16000` | Supported sound frequencies |
| `SOUND_TYPES` | `music:en-us-callie` | Sound types and languages |
| `FS_LOG_LEVEL` | `info` | FreeSWITCH core log level |
| `FS_SOFIA_LOG_LEVEL` | `0` | Sofia SIP log level |
| `FS_ESL_PASSWORD` | `ConnectNGESLPassword` | Password for mod_event_socket and the container healthcheck. The entrypoint substitutes it into the loopback-only ESL config before FreeSWITCH starts. Use the same value in any ESL client (e.g. the firewall service). |
| `FS_DOMAIN` | — | SIP / WSS domain; used to extract TLS certs from Traefik ACME and as `force-register-domain` in sofia. |

## Usage with docker-compose

```yaml
services:
  freeswitch:
    image: oduist/freeswitch:latest
    container_name: freeswitch
    hostname: freeswitch
    network_mode: host
    restart: unless-stopped
    environment:
      - ODOO_URL=http://odoo:8069
      - FS_WEBHOOK_TOKEN=${FS_WEBHOOK_TOKEN}
      - FS_ESL_PASSWORD=${FS_ESL_PASSWORD}
```

## Documentation

- [FreeSWITCH Official Docs](https://freeswitch.org/confluence/display/FREESWITCH/FreeSWITCH+Explained)
- [FreeSWITCH bootstrap and source customizations](freeswitch/README.md)
- [Odoo Connect FreeSWITCH Module](../../specs/connect_freeswitch.md)
