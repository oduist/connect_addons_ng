# 029: TLS for FreeSWITCH XML-RPC via Traefik

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
- New Boolean `freeswitch_xmlrpc_tls_verify` (default **on**) on
  `connect.settings`. When off, the context disables hostname/chain
  verification — for development behind a self-signed certificate only.
- `freeswitch_xmlrpc_port` is repurposed as the **public** Traefik HTTPS
  port (default `443`). The internal `mod_xml_rpc` listen port is a fixed
  `FS_XMLRPC_INTERNAL_PORT = 8080` constant in `controllers/freeswitch_xml.py`
  (used when serving `xml_rpc.conf`), decoupled from the public port.
- `deploy/docker-compose.yml` gains a `traefik` service plus
  `deploy/traefik/dynamic.yml`: Traefik is configured for production via
  CLI flags (env-interpolated `${FS_DOMAIN}` / `${ACME_EMAIL}`), with a
  **Let's Encrypt** resolver issuing the cert for `FS_DOMAIN` on the
  `websecure` entrypoint. The dynamic route forwards `PathPrefix(/RPC2)`
  on `websecure` to `http://host.docker.internal:8080` (FreeSWITCH runs
  `network_mode: host`, reached via the host gateway). The `traefik-acme`
  volume is shared with the fs container so its entrypoint can reuse
  Traefik's certificate for Verto. In local development (`FS_DOMAIN`
  defaults to `localhost`) ACME cannot validate, so Traefik serves its
  self-signed default cert and Odoo runs with TLS verification off.

No migration: the product has no existing installations yet (still in
development), so the field default-value change and the new Boolean apply
to fresh records directly.

[#37]: https://github.com/oduist/connect_addons_ng/issues/37
