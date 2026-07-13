# Overlay image: Dograh API + the vendored freeswitch telephony provider.
#
# Build (from connect_dograh/deploy/):
#   docker build --platform linux/amd64 --provenance=false --sbom=false \
#     --build-arg DOGRAH_BASE_IMAGE=dograhai/dograh-api:<pinned> \
#     -t oduist/dograh-api:<tag> .
#
# The registration script fails the build when the upstream provider
# registry shape has drifted — never ship an overlay that only breaks
# at runtime.

ARG DOGRAH_BASE_IMAGE=dograhai/dograh-api:latest
FROM ${DOGRAH_BASE_IMAGE}

USER root

COPY --chown=dograh:dograh providers/freeswitch /app/api/services/telephony/providers/freeswitch
COPY register_freeswitch_provider.py /tmp/register_freeswitch_provider.py
RUN python /tmp/register_freeswitch_provider.py /app \
 && rm /tmp/register_freeswitch_provider.py

USER dograh
