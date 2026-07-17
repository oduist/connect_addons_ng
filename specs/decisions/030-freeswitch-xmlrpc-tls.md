# 030: TLS for FreeSWITCH XML-RPC via Traefik

## Status

Superseded in part by ADR-043. TLS termination at Traefik remains the
decision; ADR-043 fixes the public port and verification policy, manages the
credential internally, moves Traefik to host networking, and restricts the
plain-HTTP listener to loopback.

## Problem

`_freeswitch_rpc()` built the `mod_xml_rpc` URL as
`http://user:pass@host:port/RPC2` with a hardcoded `http://` scheme
(GitHub issue [#37], rated Critical). HTTP Basic Auth sends the
credential as base64 in a header — over plain HTTP it travels in
cleartext. `mod_xml_rpc` is a control-plane interface: anyone able to
observe the network path between Odoo and FreeSWITCH (cloud operator,
peering ISP, a compromised pod on the same egress) can capture the
credential and then run arbitrary `freeswitch.api` commands (originate
calls, eavesdrop, hangup, eval). Restricting the path by source IP is
not enough — the secret must never be exposed in cleartext.

## Constraint

`mod_xml_rpc` (the bundled Abyss HTTP server) has **no native TLS**: its
config exposes only `http-port`, `auth-user`, `auth-pass`, `auth-realm`.
TLS therefore has to be terminated by something in front of it.

## Options Considered

1. **Make the scheme a setting (`http`/`https`).** Lets an operator opt
   into HTTPS but keeps `http` reachable, and still needs an external TLS
   terminator. Rejected — the product is always deployed behind Traefik,
   so a plaintext option is needless attack surface.
2. **Terminate TLS at Traefik (chosen).** FreeSWITCH is already deployed
   behind Traefik, and the `oduist/freeswitch` entrypoint already
   extracts Traefik's ACME certificate to serve Verto/WSS. Reuse the same
   Traefik edge to terminate HTTPS for XML-RPC and proxy to the internal
   `8080` plain-HTTP port. Odoo always connects over `https://`.

The file-provider router must include a host matcher rendered from
`FS_DOMAIN` as well as the `/RPC2` path prefix, and explicitly select the
`letsencrypt` certificate resolver. A path-only rule does not give ACME a
domain from which to request a certificate and leaves Traefik serving its
self-signed default. `FS_DOMAIN` is therefore passed into the Traefik
container for file-provider Go-template rendering.
3. **stunnel/nginx sidecar inside the FreeSWITCH image** terminating TLS
   with the extracted `wss.pem`. Rejected — heavier (Dockerfile +
   entrypoint changes, image rebuild/republish) for no benefit over
   reusing the Traefik edge that is already present.

## Decision

Terminate XML-RPC TLS at **Traefik** (option 2). Odoo connects to
`https://<host>:<port>/RPC2`; Traefik proxies to `mod_xml_rpc` on the
fixed internal port `8080`.

## Rationale

- One TLS edge for the whole stack: Traefik manages the certificate;
  Verto extracts it for WSS, XML-RPC is fronted by it. No second cert to
  manage, no FreeSWITCH image rebuild.
- Matches the issue's own recommendation ("a Traefik route on the FS host
  that terminates TLS in front of `:8080`").
- Clean separation of concerns: FreeSWITCH terminates the realtime media
  planes (WSS, DTLS-SRTP) itself; Traefik terminates the control-plane
  HTTP (XML-RPC).

## Implementation

- `_freeswitch_rpc()` always builds an `https://` URL and passes an
  `ssl` context to `xmlrpc.client.ServerProxy`.
- ADR-043 subsequently fixed the public port to `443`, made certificate
  verification mandatory, fixed the username to `odoo`, and made the password
  an internally generated credential rotated with the host.
- The internal `mod_xml_rpc` listen port is the fixed
  `FREESWITCH_XMLRPC_INTERNAL_PORT = 8080` package constant. The pinned image
  patches the upstream module to bind it to `127.0.0.1`.
- `deploy/docker-compose.yml` gains a `traefik` service plus
  `deploy/traefik/dynamic.yml`: Traefik is configured for production via
  CLI flags (env-interpolated `${FS_DOMAIN}` / `${ACME_EMAIL}`), with a
  **Let's Encrypt** resolver issuing the cert for `FS_DOMAIN` on the
  `websecure` entrypoint. The dynamic route matches the rendered `FS_DOMAIN`
  host plus `PathPrefix(/RPC2)` and forwards to
  `http://127.0.0.1:8080`; Traefik and FreeSWITCH both use host networking.
  The `traefik-acme`
  volume is shared with the fs container so its entrypoint can reuse
  Traefik's certificate for Verto.

[#37]: https://github.com/oduist/connect_addons_ng/issues/37
