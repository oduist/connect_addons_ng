FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libsndfile1 tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=7860

EXPOSE 7860
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["connect-pipecat-service"]
