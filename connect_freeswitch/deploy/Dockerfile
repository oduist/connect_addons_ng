###############################################################################
# Stage 1: Build mod_piper_tts
###############################################################################
FROM --platform=linux/amd64 debian:bookworm-slim AS builder

ARG PIPER_VERSION=1.2.0
ARG MOD_PIPER_TTS_VERSION=v1.0.2

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    autoconf \
    automake \
    libtool \
    pkg-config \
    git \
    ca-certificates \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Get FreeSWITCH source (headers only — needed for compilation)
RUN git clone --depth 1 https://github.com/signalwire/freeswitch.git /usr/src/freeswitch

# Bootstrap FreeSWITCH just enough to get headers and config
WORKDIR /usr/src/freeswitch
RUN ./bootstrap.sh -j && ./configure --prefix=/usr/local/freeswitch

# Clone mod_piper_tts
RUN git clone --depth 1 --branch ${MOD_PIPER_TTS_VERSION} \
    https://github.com/aks-devs/mod_piper_tts.git /usr/src/mod_piper_tts

# Compile mod_piper_tts using FreeSWITCH build system
WORKDIR /usr/src/mod_piper_tts/sources
RUN cp -r /usr/src/mod_piper_tts/sources /usr/src/freeswitch/src/mod/asr_tts/mod_piper_tts
WORKDIR /usr/src/freeswitch
RUN make -C src/mod/asr_tts/mod_piper_tts \
    MODDIR=/usr/lib/freeswitch/mod \
    MODINSTDIR=/usr/lib/freeswitch/mod

# Download piper binary
RUN curl -fSL https://github.com/rhasspy/piper/releases/download/v${PIPER_VERSION}/piper_linux_x86_64.tar.gz \
    -o /tmp/piper.tar.gz \
    && mkdir -p /opt/piper/lib \
    && tar -xzf /tmp/piper.tar.gz -C /opt/piper/lib --strip-components=1 \
    && rm /tmp/piper.tar.gz

# Download voice models (English + Russian)
RUN mkdir -p /opt/piper/models \
    && curl -fSL "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx" \
       -o /opt/piper/models/en_US-lessac-medium.onnx \
    && curl -fSL "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json" \
       -o /opt/piper/models/en_US-lessac-medium.onnx.json \
    && curl -fSL "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ru/ru_RU/irina/medium/ru_RU-irina-medium.onnx" \
       -o /opt/piper/models/ru_RU-irina-medium.onnx \
    && curl -fSL "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ru/ru_RU/irina/medium/ru_RU-irina-medium.onnx.json" \
       -o /opt/piper/models/ru_RU-irina-medium.onnx.json

###############################################################################
# Stage 2: Final image
###############################################################################
FROM --platform=linux/amd64 safarov/freeswitch:latest

# Copy compiled mod_piper_tts module
COPY --from=builder /usr/src/freeswitch/src/mod/asr_tts/mod_piper_tts/.libs/mod_piper_tts.so \
    /usr/lib/freeswitch/mod/mod_piper_tts.so

# Copy piper binary and its libs
COPY --from=builder /opt/piper/lib /opt/piper/lib

# Copy voice models
COPY --from=builder /opt/piper/models /opt/piper/models

# Copy FreeSWITCH configuration files
COPY freeswitch/conf /etc/freeswitch

# Set default environment variables
ENV SOUND_RATES=8000:16000 \
    SOUND_TYPES=music:en-us-callie \
    EPMD=false \
    DUMPCAP=false \
    ODOO_URL=http://localhost:8069 \
    FS_LOG_LEVEL=info \
    FS_SOFIA_LOG_LEVEL=0

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD fs_cli -x "status" > /dev/null 2>&1 || exit 1

# Run FreeSWITCH
CMD ["freeswitch", "-c"]
