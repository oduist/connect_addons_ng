FROM python:3.12-alpine

RUN apk add --no-cache curl tini

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1 \
    HTTP_BIND_HOST=0.0.0.0 \
    HTTP_BIND_PORT=8083 \
    STATE_PATH=/var/lib/connect-3cx/state.json

VOLUME ["/var/lib/connect-3cx"]
EXPOSE 8083

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD curl -fsS http://127.0.0.1:8083/healthz || exit 1

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["connect-3cx-agent"]
