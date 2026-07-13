FROM python:3.12-alpine

RUN apk add --no-cache curl tini

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1 \
    HTTP_BIND_HOST=0.0.0.0 \
    HTTP_BIND_PORT=8082 \
    STATE_PATH=/var/lib/connect-asterisk/state.json

VOLUME ["/var/lib/connect-asterisk"]
EXPOSE 8082

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD curl -fsS http://127.0.0.1:8082/healthz || exit 1

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["connect-asterisk-agent"]
