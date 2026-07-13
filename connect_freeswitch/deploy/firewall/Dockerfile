FROM python:3.12-alpine

# The iptables package ships ip6tables on Alpine >= 3.19; the assertion
# fails the build if a future base image drops it (IPv6 support relies
# on it, see ADR-037).
RUN apk add --no-cache iptables ipset curl tini && command -v ip6tables

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
