# FreeSWITCH Docker Image

Docker image of FreeSWITCH with configuration for integration with Odoo connect_freeswitch module.

Includes [mod_piper_tts](https://github.com/aks-devs/mod_piper_tts) for local neural text-to-speech via [Piper](https://github.com/rhasspy/piper), compiled in a multi-stage Docker build with English and Russian voice models.

## Building the Image

```bash
# In the deploy/ folder
docker build -t oduist/freeswitch:latest .
```

## Running the Container

### With ODOO_URL Specified

```bash
docker run -d \
  --name freeswitch \
  --net host \
  -e ODOO_URL=http://localhost:8069 \
  -v freeswitch-sounds:/usr/share/freeswitch/sounds \
  -v $(pwd)/freeswitch/conf:/etc/freeswitch \
  -v $(pwd)/freeswitch/logs:/var/log/freeswitch \
  oduist/freeswitch:latest
```

### Examples with Different ODOO_URLs

```bash
# Locally
docker run -d --name freeswitch --net host -e ODOO_URL=http://localhost:8069 oduist/freeswitch:latest

# Remote server
docker run -d --name freeswitch --net host -e ODOO_URL=http://192.168.1.100:8069 oduist/freeswitch:latest

# With port
docker run -d --name freeswitch --net host -e ODOO_URL=https://odoo.example.com:8069 oduist/freeswitch:latest
```

## Checking Status

```bash
docker logs freeswitch
docker exec freeswitch fs_cli -x "status"
```

## Stopping the Container

```bash
docker stop freeswitch
docker rm freeswitch
```

## Publishing the Image

```bash
# Already done via 'docker login'
docker push oduist/freeswitch:latest
```

## Environment Variables

| Variable | Default Value | Description |
|---|---|---|
| `ODOO_URL` | `http://localhost:8069` | URL of Odoo server for webhooks |
| `SOUND_RATES` | `8000:16000` | Supported sound frequencies |
| `SOUND_TYPES` | `music:en-us-callie` | Sound types and languages |
| `EPMD` | `false` | Erlang Port Mapper Daemon |
| `DUMPCAP` | `false` | Packet capture tool |

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
    volumes:
      - freeswitch-sounds:/usr/share/freeswitch/sounds
      - ./freeswitch/conf:/etc/freeswitch
      - ./freeswitch/logs:/var/log/freeswitch
```

## Documentation

- [FreeSWITCH Official Docs](https://freeswitch.org/confluence/display/FREESWITCH/FreeSWITCH+Explained)
- [Odoo Connect FreeSWITCH Module](../specs/connect_freeswitch.md)
