# The LiveKit Agents runtime and its plugins (silero VAD via onnxruntime,
# turn detection) need glibc — use the slim Debian image, not alpine.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir .

# Pre-download the plugin model files (silero VAD, turn detector) so the
# first call does not stall fetching them.
RUN connect-livekit-agent run --help >/dev/null 2>&1 || true

ENV PYTHONUNBUFFERED=1 \
    EGRESS_OUT_DIR=/out \
    STATE_DIR=/state

# `run` (agent worker) or `upload-recordings` (egress uploader).
ENTRYPOINT ["connect-livekit-agent"]
CMD ["run"]
