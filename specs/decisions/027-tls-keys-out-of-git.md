# ADR-027: Generate FreeSWITCH TLS/DTLS material at runtime, never commit it

## Status
Accepted

## Context

The audit found two real RSA-4096 private keys committed to the repo:

- `connect_freeswitch/deploy/freeswitch/conf/tls/wss.pem` — the WSS
  certificate+key for the Verto WebRTC signaling socket;
- `connect_freeswitch/deploy/freeswitch/conf/tls/dtls-srtp.pem` — the
  DTLS-SRTP key used for WebRTC media key exchange.

`Dockerfile:207` does `COPY freeswitch/conf/ /usr/local/freeswitch/etc/freeswitch/`,
and `TLS_DIR=/usr/local/freeswitch/etc/freeswitch/tls`, so the committed
keys landed exactly where the entrypoint looks. The entrypoint's
self-signed fallback only fires `if [ ! -f "$TLS_DIR/wss.pem" ]`, so with
the file always present the fallback never ran and the **same committed
private key shipped in every published `oduist/freeswitch` image**. Anyone
with the public repo or image could impersonate the WSS endpoint and
MITM/decrypt WebRTC media for any deployment on the default cert.

## Decision

TLS material is runtime-generated, never stored in git:

1. Remove both `.pem` files from the repo (`git rm`).
2. Gitignore `connect_freeswitch/deploy/freeswitch/conf/tls/*.pem` so they
   cannot be re-committed.
3. Rely on the existing `setup_tls()` entrypoint logic, which already
   (a) extracts a real certificate from Traefik's `acme.json` when
   `FS_DOMAIN` + ACME are present, or (b) generates a self-signed
   cert+key into `TLS_DIR` when none exists. With the committed file gone,
   the fallback now fires on a fresh container.

No entrypoint change is required — the generation path already existed and
was simply masked by the committed file.

## Consequences

- **The previously committed keys are compromised** (they were public).
  Rebuilding the image drops them; any deployment that ran an old image
  must redeploy on a rebuilt image so a fresh key is generated. Production
  deployments fronted by Traefik/ACME already serve a real cert and were
  never using the committed key for the public hostname, but the
  DTLS-SRTP media key was the committed one until this change.
- A fresh self-signed cert is generated per container on first boot when
  ACME is not configured; WebRTC clients that pinned the old cert must
  re-trust (none should, in practice).
- Image must be rebuilt for the change to take effect (the key is dropped
  from the build context); see the deploy-folder rebuild policy in
  CLAUDE.md.
