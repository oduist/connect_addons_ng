# FreeSWITCH Docker Image

FreeSWITCH built from source (`v1.10.12`) with only the modules needed for Odoo integration.

Includes [mod_piper_tts](https://github.com/aks-devs/mod_piper_tts) for local neural text-to-speech via [Piper](https://github.com/rhasspy/piper) with English and Russian voice models.

## What's Inside

Built from source with a minimal module set:

| Category | Modules |
|----------|---------|
| Loggers | mod_logfile |
| XML Interfaces | mod_xml_curl, mod_xml_cdr |
| Event Handlers | mod_event_socket |
| Endpoints | mod_sofia, mod_loopback, mod_rtc, mod_verto |
| Applications | mod_commands, mod_dptools, mod_http_cache, mod_dialplan_xml |
| Codecs | mod_opus, mod_spandsp |
| File Formats | mod_sndfile, mod_native_file, mod_tone_stream |
| TTS | mod_piper_tts |

To add a module: edit `modules.conf` in the Dockerfile, add config in `freeswitch/conf/autoload_configs/`, rebuild.

## Building the Image

```bash
cd connect_freeswitch/deploy
docker build --platform linux/amd64 -t oduist/freeswitch:1.0.3 -t oduist/freeswitch:latest .
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
docker exec freeswitch fs_cli -x "status"
```

## Publishing the Image

```bash
docker push oduist/freeswitch:1.0.3
docker push oduist/freeswitch:latest
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ODOO_URL` | `http://localhost:8069` | URL of Odoo server for webhooks |
| `SOUND_RATES` | `8000:16000` | Supported sound frequencies |
| `SOUND_TYPES` | `music:en-us-callie` | Sound types and languages |
| `FS_LOG_LEVEL` | `info` | FreeSWITCH core log level |
| `FS_SOFIA_LOG_LEVEL` | `0` | Sofia SIP log level |
| `FS_ESL_PASSWORD` | `ClueCon` | Password for mod_event_socket. When set, the entrypoint substitutes it into `autoload_configs/event_socket.conf.xml` before FreeSWITCH starts. Use the same value in any ESL client (e.g. the firewall service). |
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
```

## Documentation

- [FreeSWITCH Official Docs](https://freeswitch.org/confluence/display/FREESWITCH/FreeSWITCH+Explained)
- [Odoo Connect FreeSWITCH Module](../specs/connect_freeswitch.md)
