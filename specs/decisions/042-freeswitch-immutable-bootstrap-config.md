# 042: Keep the FreeSWITCH bootstrap configuration inside the image

## Status

Accepted

## Problem

The production Compose example bind-mounted the host directory
`./freeswitch/conf` over the complete FreeSWITCH configuration directory in
`oduist/freeswitch`. That image already contains a curated bootstrap
configuration, but the mount silently replaced it with whatever happened to
be present on the host. A host copied from an upstream FreeSWITCH image could
therefore disable `mod_xml_curl`, `mod_xml_cdr`, `mod_xml_rpc`, and `mod_curl`,
drop the `ODOO_URL` / `FS_WEBHOOK_TOKEN` variable mapping, and expose ESL on a
non-loopback address.

The image healthcheck also ran `fs_cli` with its default ESL password. The
entrypoint supports a deployment-specific `FS_ESL_PASSWORD`, so every
correctly customized deployment was reported as unhealthy even while
FreeSWITCH and its ESL clients were working.

## Configuration boundary

Odoo provides the dynamic PBX configuration through `mod_xml_curl`: users,
extensions, gateways, dialplan entries, ACL data, and other database-backed
records. FreeSWITCH still needs a small static bootstrap before it can ask
Odoo for any of that data. The bootstrap loads the required modules, maps
environment variables, defines the XML-curl/CDR endpoints, binds SIP/Verto,
and keeps ESL on loopback.

## Options considered

1. **Keep a writable full-directory bind mount.** This makes bootstrap edits
   possible without rebuilding but permits unversioned host state to replace
   security and integration defaults. Rejected.
2. **Mount selected individual files read-only.** This narrows the risk but
   still creates a second, host-managed copy of versioned image configuration
   with no production requirement. Rejected as the default; an operator can
   add an explicit override for an exceptional deployment.
3. **Bake the bootstrap into the versioned image (chosen).** Deployments pass
   only environment variables and mount data that must persist or be shared
   (sounds and Traefik ACME state).

## Decision

- `oduist/freeswitch` owns its complete static bootstrap configuration.
- Production Compose must not mount a host directory over
  `/usr/local/freeswitch/etc/freeswitch`.
- Odoo remains the source of truth for dynamic PBX configuration through
  `mod_xml_curl`.
- `mod_event_socket` listens on `127.0.0.1:8021`; it is reachable by the
  colocated host-network firewall service but not from the public network.
- The image healthcheck authenticates `fs_cli` with the runtime
  `FS_ESL_PASSWORD`, falling back to the baked ESL password when the variable
  is unset.

## Consequences

- Bootstrap changes require an image rebuild and a new image tag, which makes
  the running configuration reproducible and reviewable.
- Removing the mount restores the image's loopback-only ESL binding and Odoo
  integration modules on existing deployments after container recreation.
- Runtime-generated TLS files are container-local. Production certificates
  are reconstructed on every start from the shared Traefik ACME volume; the
  self-signed fallback may change when a development container is recreated.
- A custom bootstrap remains possible through an explicit derived image,
  which preserves versioning and review instead of relying on mutable host
  files.
