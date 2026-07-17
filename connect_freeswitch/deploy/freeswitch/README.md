# FreeSWITCH bootstrap and source customizations

This directory contains the static FreeSWITCH bootstrap copied into
`oduist/freeswitch`. It is intentionally small: FreeSWITCH needs it before it
can contact Odoo, while Odoo remains the source of truth for database-backed
PBX configuration.

## Configuration boundary

The image owns these bootstrap responsibilities:

- load the curated modules, including `mod_xml_curl`, `mod_xml_cdr`,
  `mod_xml_rpc`, `mod_event_socket`, Sofia, Verto, Piper TTS, and the vendored
  `mod_audio_fork`;
- map `ODOO_URL`, `FS_WEBHOOK_TOKEN`, `FS_DOMAIN`, and the logging settings
  into FreeSWITCH variables;
- define the Odoo XML-curl and CDR endpoints;
- bind SIP, Verto, and the loopback-only ESL listener;
- provide the minimum local directory and dialplan required to bootstrap.

Odoo supplies dynamic directory users, endpoints, gateways, ACLs, extensions,
call flows, and dialplan entries through `mod_xml_curl`.

Do not mount a host directory over
`/usr/local/freeswitch/etc/freeswitch` in production. A full-directory mount
replaces this versioned bootstrap and can disable Odoo integration or restore
unsafe listener defaults. Use a derived image for a reviewed static override.

## Changes carried by the image

The image is not an unmodified upstream FreeSWITCH build. The deployment
currently carries these deliberate changes:

1. FreeSWITCH is built from the pinned `v1.10.12` source tag with the module
   list declared in `../Dockerfile`.
2. `../patches/mod_xml_rpc-loopback.patch` changes upstream `mod_xml_rpc` to
   create its Abyss socket on `127.0.0.1:8080`. Upstream exposes only an
   `http-port` setting and otherwise binds every interface. Traefik shares the
   host network namespace, terminates HTTPS, and is the only public route to
   this plain-HTTP management listener (ADR-043).
3. `conf/autoload_configs/event_socket.conf.xml` binds ESL to
   `127.0.0.1:8021`. The entrypoint substitutes the runtime
   `FS_ESL_PASSWORD`, and the Docker healthcheck authenticates with the same
   value (ADR-042).
4. FreeSWITCH-to-Odoo HTTP calls authenticate with the Odoo-generated
   `freeswitch_webhook_token`, supplied to the container as
   `FS_WEBHOOK_TOKEN` (ADR-025 and ADR-044).
5. The entrypoint extracts the certificate for `FS_DOMAIN` from Traefik's
   shared ACME store for Verto WSS and DTLS-SRTP, with a self-signed fallback
   for development.

## Patch maintenance

The Docker build runs `git apply --check` before applying the XML-RPC patch.
If the pinned FreeSWITCH version changes, inspect the new upstream
`src/mod/xml_int/mod_xml_rpc/mod_xml_rpc.c`, rebase the patch deliberately,
and confirm that the resulting process still listens only on loopback.

Minimum runtime verification on a host-network deployment:

```bash
docker exec freeswitch sh -c 'fs_cli -p "$FS_ESL_PASSWORD" -x status'
ss -ltnp | grep -E '127\.0\.0\.1:(8021|8080)'
curl --fail --silent --show-error https://<freeswitch-host>/RPC2 \
  --output /dev/null
```

The unauthenticated public XML-RPC request may return `401`; that still proves
the TLS route reaches `mod_xml_rpc`. There must be no `0.0.0.0:8021` or
`0.0.0.0:8080` listener.

## Change checklist

When changing this directory or the source patch:

1. update the corresponding ADR, `specs/connect_freeswitch.md`, and admin
   deployment documentation;
2. build the image from `connect_freeswitch/deploy/` using the short module
   release tag documented in `AGENTS.md`;
3. test the ESL healthcheck, XML-curl authentication, loopback listeners, and
   public Traefik route;
4. publish only the FreeSWITCH image unless the firewall image sources also
   changed.

See the parent [deployment README](../README.md) for build, runtime, and image
publishing commands.
