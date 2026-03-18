###############################################################################
# Stage 1: Build FreeSWITCH + mod_piper_tts from source
###############################################################################
FROM --platform=linux/amd64 debian:bookworm AS builder

ARG FS_VERSION=v1.10.12
ARG PIPER_VERSION=1.2.0
ARG MOD_PIPER_TTS_VERSION=v1.0.2

# Build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential autoconf automake libtool pkg-config cmake \
    git ca-certificates curl wget python3 yasm \
    # FreeSWITCH core
    libssl-dev libcurl4-openssl-dev libpcre3-dev libsqlite3-dev \
    libedit-dev zlib1g-dev uuid-dev libspeexdsp-dev \
    # Module deps
    libopus-dev libsndfile1-dev libtiff-dev libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

# ── Build libks2 (needed for mod_verto, mod_rtc) ────────────────────────────
RUN git clone --depth 1 https://github.com/signalwire/libks.git /usr/src/libks \
    && cd /usr/src/libks \
    && cmake -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_BUILD_TYPE=Release . \
    && make -j$(nproc) && make install

# ── Build sofia-sip (removed from FS tree since v1.10.4) ────────────────────
RUN git clone --depth 1 https://github.com/freeswitch/sofia-sip.git /usr/src/sofia-sip \
    && cd /usr/src/sofia-sip \
    && ./bootstrap.sh \
    && ./configure --prefix=/usr \
    && make -j$(nproc) && make install

# ── Build spandsp (removed from FS tree since v1.10.4) ──────────────────────
RUN git clone --depth 1 https://github.com/freeswitch/spandsp.git /usr/src/spandsp \
    && cd /usr/src/spandsp \
    && ./bootstrap.sh \
    && ./configure --prefix=/usr \
    && make -j$(nproc) && make install

RUN ldconfig

# ── Clone FreeSWITCH ────────────────────────────────────────────────────────
RUN git clone --depth 1 --branch ${FS_VERSION} \
    https://github.com/signalwire/freeswitch.git /usr/src/freeswitch

# ── Add mod_piper_tts to the source tree ────────────────────────────────────
RUN git clone --depth 1 --branch ${MOD_PIPER_TTS_VERSION} \
    https://github.com/aks-devs/mod_piper_tts.git /tmp/mod_piper_tts \
    && cp -r /tmp/mod_piper_tts/sources \
       /usr/src/freeswitch/src/mod/asr_tts/mod_piper_tts

# ── Configure modules to build (only what we use) ───────────────────────────
WORKDIR /usr/src/freeswitch

RUN cat > modules.conf <<'MODULES'
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
MODULES

# ── Build FreeSWITCH ────────────────────────────────────────────────────────
RUN ./bootstrap.sh -j
RUN ./configure \
    --prefix=/usr/local/freeswitch \
    --enable-core-pgsql-support=no \
    --without-python \
    --without-erlang \
    --without-java
RUN make -j$(nproc)
RUN make install

# ── Download piper binary ───────────────────────────────────────────────────
RUN curl -fSL \
    https://github.com/rhasspy/piper/releases/download/v${PIPER_VERSION}/piper_linux_x86_64.tar.gz \
    -o /tmp/piper.tar.gz \
    && mkdir -p /opt/piper \
    && tar -xzf /tmp/piper.tar.gz -C /opt/piper --strip-components=1 \
    && rm /tmp/piper.tar.gz

# ── Download voice models (English + Russian) ───────────────────────────────
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
# Stage 2: Minimal runtime image
###############################################################################
FROM --platform=linux/amd64 debian:bookworm-slim

# Runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl3 libcurl4 libpcre3 libsqlite3-0 \
    libedit2 zlib1g libuuid1 libspeexdsp1 \
    libopus0 libsndfile1 libtiff6 libjpeg62-turbo \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# FreeSWITCH installation
COPY --from=builder /usr/local/freeswitch /usr/local/freeswitch

# Shared libraries built from source (sofia-sip, spandsp, libks)
COPY --from=builder /usr/lib/libsofia-sip-ua* /usr/lib/
COPY --from=builder /usr/lib/libspandsp* /usr/lib/
COPY --from=builder /usr/lib/libks* /usr/lib/

# Piper TTS binary + voice models
COPY --from=builder /opt/piper /opt/piper

RUN ldconfig

# Convenience symlinks
RUN ln -sf /usr/local/freeswitch/bin/freeswitch /usr/bin/freeswitch \
    && ln -sf /usr/local/freeswitch/bin/fs_cli /usr/bin/fs_cli

# Copy FreeSWITCH configuration
COPY freeswitch/conf /usr/local/freeswitch/conf

ENV ODOO_URL=http://localhost:8069 \
    SOUND_RATES=8000:16000 \
    SOUND_TYPES=music:en-us-callie \
    FS_LOG_LEVEL=info \
    FS_SOFIA_LOG_LEVEL=0

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD fs_cli -x "status" > /dev/null 2>&1 || exit 1

CMD ["freeswitch", "-c"]
