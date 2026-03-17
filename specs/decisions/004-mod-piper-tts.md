# ADR-004: Add mod_piper_tts to FreeSWITCH Docker Image

## Status
Accepted

## Context
We need local text-to-speech capability in FreeSWITCH for IVR prompts and announcements without depending on cloud TTS services. The `mod_piper_tts` module integrates [Piper](https://github.com/rhasspy/piper) — a fast, local neural TTS engine — directly into FreeSWITCH.

## Options Considered

### 1. mod_tts_commandline + external piper binary
- Pros: No custom module compilation needed
- Cons: Spawns a process per TTS call, slower, no caching built in

### 2. mod_piper_tts (chosen)
- Pros: Native FreeSWITCH integration, built-in MD5 caching, direct piper invocation, language-model mapping in config
- Cons: Requires compiling a C module against FreeSWITCH headers

### 3. Cloud TTS (Google, AWS Polly)
- Pros: High quality voices
- Cons: Adds cloud dependency, latency, cost — contradicts our local-first approach

## Decision
Use [mod_piper_tts](https://github.com/aks-devs/mod_piper_tts) v1.0.2 compiled in a multi-stage Docker build. Ship with English (`en_US-lessac-medium`) and Russian (`ru_RU-irina-medium`) voice models from [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices).

## Implementation

### Docker build strategy
The `safarov/freeswitch:latest` base image is a minimal `FROM scratch` image with no compiler or package manager. We use a multi-stage build:

1. **Stage 1 (builder)**: Debian-based image with FreeSWITCH dev packages, gcc, and build tools. Clones mod_piper_tts, compiles `mod_piper_tts.so`. Downloads piper binary (v1.2.0 amd64) and voice models.
2. **Stage 2 (final)**: Copies compiled `.so`, piper binary, and models into the production image.

### Configuration
- `piper_tts.conf.xml` in `autoload_configs/` defines piper binary path, cache settings, and language-to-model mappings
- `mod_piper_tts` added to `modules.conf.xml`
- Voice models stored in `/opt/piper/models/`

### Usage in dialplan
```xml
<action application="speak" data="piper|en|Hello, please hold."/>
<action application="speak" data="piper|ru|Здравствуйте, пожалуйста подождите."/>
```

## Consequences
- Docker image size increases (~150MB for piper binary + models)
- No cloud dependency for TTS
- Additional voice models can be added by downloading `.onnx` + `.onnx.json` files and updating `piper_tts.conf.xml`
