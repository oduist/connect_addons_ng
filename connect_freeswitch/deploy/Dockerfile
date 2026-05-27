###############################################################################
# Stage 1: Build FreeSWITCH + mod_piper_tts from source
###############################################################################
FROM debian:bookworm AS builder

ARG FS_VERSION=v1.10.12
ARG PIPER_VERSION=1.2.0
ARG MOD_PIPER_TTS_VERSION=v1.0.2

# Build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential autoconf automake libtool libtool-bin pkg-config cmake \
    git ca-certificates curl wget python3 yasm \
    # FreeSWITCH core
    libssl-dev libcurl4-openssl-dev libpcre3-dev libsqlite3-dev \
    libedit-dev zlib1g-dev uuid-dev libspeex-dev libspeexdsp-dev \
    # Module deps
    libopus-dev libsndfile1-dev libtiff-dev libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

# ── Build libks2 (needed for mod_verto, mod_rtc) ────────────────────────────
RUN git clone --depth 2 --branch v2.0.10 https://github.com/signalwire/libks.git /usr/src/libks \
    && cd /usr/src/libks \
    && GIT_COMMITTER_NAME=build GIT_COMMITTER_EMAIL=build@build git tag -a v2.0.10 -m "v2.0.10" --force \
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

# ── Bootstrap FreeSWITCH (cached independently of module list) ─────────────
WORKDIR /usr/src/freeswitch

RUN ./bootstrap.sh -j

# ── Module list (changing this invalidates configure + make, but not bootstrap)
RUN cat > modules.conf <<'MODULES'
loggers/mod_logfile
xml_int/mod_xml_curl
xml_int/mod_xml_cdr
xml_int/mod_xml_rpc
event_handlers/mod_event_socket
endpoints/mod_sofia
endpoints/mod_loopback
endpoints/mod_rtc
endpoints/mod_verto
applications/mod_commands
applications/mod_curl
applications/mod_dptools
applications/mod_http_cache
applications/mod_fifo
applications/mod_valet_parking
formats/mod_local_stream
dialplans/mod_dialplan_xml
codecs/mod_opus
formats/mod_sndfile
formats/mod_native_file
formats/mod_tone_stream
asr_tts/mod_piper_tts
MODULES

RUN ./configure \
    --prefix=/usr/local/freeswitch \
    --enable-core-pgsql-support=no \
    --without-python \
    --without-erlang \
    --without-java
RUN make -j$(nproc)
RUN make install

# ── Collect all shared library dependencies automatically ────────────────────
# Scan all FS binaries/modules with ldd, extract resolved lib paths (the path
# after "=>"), and copy them into a staging dir for the runtime image.
RUN mkdir -p /staging/usr/lib \
    && find /usr/local/freeswitch/bin /usr/local/freeswitch/lib -type f \( -executable -o -name '*.so*' \) \
       -exec ldd {} + 2>/dev/null \
       | awk '/=>/ && /\// { for(i=1;i<=NF;i++) if($i ~ /^\//) print $i }' \
       | sort -u \
       | while read lib; do \
           case "$(basename "$lib")" in \
               libc.so*|libm.so*|libpthread*|libdl*|librt.so*|ld-linux*) continue ;; \
           esac; \
           cp -vL "$(readlink -f "$lib")" "/staging/usr/lib/$(basename "$lib")" || true; \
       done \
    && ldconfig -N /staging/usr/lib

# ── Download piper binary ───────────────────────────────────────────────────
RUN curl -fSL \
    https://github.com/rhasspy/piper/releases/download/v${PIPER_VERSION}/piper_amd64.tar.gz \
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
FROM debian:bookworm-slim

# Minimal runtime packages (libc, libgcc, etc. already in base image)
# python3 is needed for ACME cert extraction at startup
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates wget python3 openssl \
    && rm -rf /var/lib/apt/lists/*

# FreeSWITCH installation
COPY --from=builder /usr/local/freeswitch /usr/local/freeswitch

# All shared library dependencies (auto-collected via ldd in builder stage)
COPY --from=builder /staging/usr/lib/ /usr/lib/

# Piper TTS binary + voice models
COPY --from=builder /opt/piper /opt/piper

RUN ldconfig

# Required runtime directories. The entrypoint downloads sound tarballs into
# /usr/share/freeswitch/sounds (mounted as a volume), but mod_local_stream
# resolves $${sounds_dir} which points inside the FreeSWITCH prefix, so we
# expose the same path under both locations via a symlink.
RUN mkdir -p /usr/local/freeswitch/var/run/freeswitch \
             /usr/local/freeswitch/var/log/freeswitch \
             /usr/share/freeswitch/sounds \
    && rm -rf /usr/local/freeswitch/share/freeswitch/sounds \
    && ln -s /usr/share/freeswitch/sounds /usr/local/freeswitch/share/freeswitch/sounds

# Convenience symlinks
RUN ln -sf /usr/local/freeswitch/bin/freeswitch /usr/bin/freeswitch \
    && ln -sf /usr/local/freeswitch/bin/fs_cli /usr/bin/fs_cli

# Replace vanilla config with our custom config
RUN rm -rf /usr/local/freeswitch/etc/freeswitch/*
COPY freeswitch/conf/ /usr/local/freeswitch/etc/freeswitch/

# Copy entrypoint
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENV ODOO_URL=http://localhost:8069 \
    SOUND_RATES=8000:16000:32000:48000 \
    SOUND_TYPES=music:en-us-callie \
    EPMD=false \
    DUMPCAP=false \
    FS_DOMAIN=localhost \
    FS_LOG_LEVEL=info \
    FS_SOFIA_LOG_LEVEL=0

VOLUME ["/usr/share/freeswitch/sounds"]

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD fs_cli -x "status" | grep -q ^UP || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]
