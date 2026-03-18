# ADR-004: Build FreeSWITCH from Source with mod_piper_tts

## Status
Accepted

## Context
We need local text-to-speech capability in FreeSWITCH for IVR prompts and announcements without depending on cloud TTS services. Additionally, the previous Docker image based on `safarov/freeswitch:latest` (a minimal `FROM scratch` image) gives us no control over the FreeSWITCH build — we can't add modules, update dependencies, or debug library issues. Building from source gives full control over the exact module set and dependencies.

## Options Considered

### 1. safarov/freeswitch + mod_piper_tts overlay
- Pros: Simple Dockerfile, small image
- Cons: No control over FS version or build options, opaque base image, adding modules requires matching exact FS version for ABI compatibility

### 2. FreeSWITCH from source with mod_piper_tts (chosen)
- Pros: Full control over modules and dependencies, reproducible builds, only the modules we actually use
- Cons: Longer build time, more complex Dockerfile, must maintain dependency versions

### 3. Cloud TTS (Google, AWS Polly)
- Pros: High quality voices
- Cons: Adds cloud dependency, latency, cost — contradicts our local-first approach

## Decision
Build FreeSWITCH v1.10.12 from source in a multi-stage Docker build with only the modules we use. Include [mod_piper_tts](https://github.com/aks-devs/mod_piper_tts) v1.0.2 for local neural TTS via [Piper](https://github.com/rhasspy/piper) v1.2.0. Ship with English (`en_US-lessac-medium`) and Russian (`ru_RU-irina-medium`) voice models.

## Implementation

### Docker build strategy
Multi-stage build on `debian:bookworm`:

**Stage 1 (builder):**
1. Install build tools and dev libraries
2. Build dependencies removed from FS tree since v1.10.4:
   - [libks2](https://github.com/signalwire/libks) — needed for mod_verto, mod_rtc
   - [sofia-sip](https://github.com/freeswitch/sofia-sip) — needed for mod_sofia
   - [spandsp](https://github.com/freeswitch/spandsp) — needed for mod_spandsp
3. Clone FreeSWITCH v1.10.12, add mod_piper_tts to source tree
4. Configure and build with exact `modules.conf` (17 modules, nothing extra)
5. Download piper binary and voice models

**Stage 2 (runtime):**
`debian:bookworm-slim` with only runtime shared libraries. Copy FS installation, piper binary, and models from builder.

### Module set (modules.conf)
Only modules matching our `autoload_configs/`:
```
loggers/mod_logfile
xml_int/mod_xml_curl
xml_int/mod_xml_cdr
event_handlers/mod_event_socket
endpoints/mod_sofia
endpoints/mod_loopback
endpoints/mod_rtc
endpoints/mod_verto
applications/mod_commands
applications/mod_dptools
applications/mod_http_cache
dialplans/mod_dialplan_xml
codecs/mod_opus
codecs/mod_spandsp
formats/mod_sndfile
formats/mod_native_file
formats/mod_tone_stream
asr_tts/mod_piper_tts
```

### Configuration
- `piper_tts.conf.xml` in `autoload_configs/` defines piper binary path (`/opt/piper/piper`), cache settings, and language-to-model mappings
- Voice models in `/opt/piper/models/`
- FreeSWITCH installed to `/usr/local/freeswitch`

### Usage in dialplan
```xml
<action application="speak" data="piper|en|Hello, please hold."/>
<action application="speak" data="piper|ru|Здравствуйте, пожалуйста подождите."/>
```

## Consequences
- Full control over FreeSWITCH build — adding/removing modules requires rebuilding the image
- Docker build takes longer (~10-15 min) but is cached in layers
- Image size is larger than the minimal `safarov/freeswitch` but contains only what we need
- No cloud dependency for TTS
- To add a module: add it to `modules.conf` in Dockerfile, add config in `autoload_configs/`, rebuild
- To add a voice model: download `.onnx` + `.onnx.json`, update `piper_tts.conf.xml`
