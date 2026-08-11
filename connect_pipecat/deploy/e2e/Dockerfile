FROM debian:bookworm AS sipp-builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential ca-certificates cmake git libncurses-dev libpcap-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch v3.7.3 https://github.com/SIPp/sipp.git /src/sipp \
    && cmake -S /src/sipp -B /src/sipp/build -DUSE_PCAP=1 \
    && cmake --build /src/sipp/build --parallel \
    && install /src/sipp/build/sipp /usr/local/bin/sipp

FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        espeak-ng ffmpeg libncursesw6 libpcap0.8 libssl3 python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /e2e
COPY --from=sipp-builder /usr/local/bin/sipp /usr/local/bin/sipp
COPY scenario.xml make_pcap.py run.sh ./
RUN chmod +x run.sh

ENTRYPOINT ["/e2e/run.sh"]
