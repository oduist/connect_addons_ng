FROM python:3.12-alpine

RUN apk add --no-cache iptables ipset curl tini

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/
COPY dashboard/ ./dashboard/

RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1 \
    HTTP_BIND_HOST=0.0.0.0 \
    HTTP_BIND_PORT=8081 \
    CONFIG_CACHE_PATH=/var/lib/connect-firewall/config.json

VOLUME ["/var/lib/connect-firewall"]
EXPOSE 8081

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["connect-firewall-service"]
