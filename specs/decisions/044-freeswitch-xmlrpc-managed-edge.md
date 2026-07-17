# ADR-044: Managed FreeSWITCH XML-RPC edge

## Status

Accepted.

## Context

Odoo controls FreeSWITCH through `mod_xml_rpc`. The module exposes the full
FreeSWITCH API over HTTP Basic authentication, but it does not implement TLS.
ADR-030 therefore placed Traefik in front of it.

The previous configuration still exposed implementation details in Odoo:
administrators could edit the public port, username, password, and TLS
verification flag. This allowed invalid and unsafe combinations, including
pointing Odoo at the internal plain-HTTP port.

The standard FreeSWITCH 1.10.12 `mod_xml_rpc` implementation has another
limitation: it accepts an `http-port` setting but no listen address. It calls
the xmlrpc-c Abyss `ServerCreate` API, which binds the port on every interface.
With `network_mode: host`, this appears as `0.0.0.0:8080` on the host.

FreeSWITCH and its firewall agent already use the host network namespace for
SIP, RTP, and host firewall management. Keeping Traefik on a bridge network
requires `host.docker.internal` and also prevents a loopback-only XML-RPC
listener from being reachable by the proxy.

## Decision

The FreeSWITCH XML-RPC integration has one supported production topology:

- Odoo stores only the public XML-RPC hostname.
- Odoo always connects to `https://<host>:443/RPC2` and always verifies the
  server certificate.
- The XML-RPC username is the internal constant `odoo`.
- The XML-RPC password remains an admin-only stored field, is never displayed
  or editable, and is generated with `secrets.token_urlsafe(32)`.
- Changing the normalized XML-RPC hostname rotates the stored password.
- FreeSWITCH receives the fixed username and current generated password from
  Odoo through `mod_xml_curl` when loading `xml_rpc.conf`.
- The pinned FreeSWITCH source build carries a minimal patch that makes
  `mod_xml_rpc` create its Abyss listener on `127.0.0.1:8080`.
- Traefik uses `network_mode: host` and proxies the public HTTPS route to
  `http://127.0.0.1:8080`.

The password and hostname change are deliberately coupled. A newly configured
host receives a fresh credential when FreeSWITCH starts and fetches its XML
configuration. Changing the host for an already running deployment requires a
FreeSWITCH restart so the module loads the rotated credential.

The upgrade migration removes the obsolete connection columns and rotates any
legacy operator-managed password once. The deployment must restart FreeSWITCH
after upgrading the Odoo module for the same reason.

## Alternatives considered

### Keep all connection fields configurable

Rejected. The supported deployment has one TLS topology, and the extra fields
make unsafe or nonsensical combinations possible.

### Leave `mod_xml_rpc` on all interfaces and rely only on the cloud firewall

Rejected. Perimeter filtering remains useful defence in depth, but the process
should not accept direct management connections on public host interfaces.

### Keep Traefik bridged and use `host.docker.internal`

Rejected. A bridged Traefik cannot reach a listener restricted to the host
loopback interface. Host networking also removes platform-specific host-gateway
plumbing from this already host-networked telephony stack.

### Patch all of xmlrpc-c with a configurable bind API

Rejected. The product needs one fixed loopback listener. A narrow patch in the
pinned `mod_xml_rpc` build has less scope and is easier to audit.

## Consequences

- XML-RPC is reachable externally only through Traefik HTTPS.
- Odoo administrators cannot view or choose the management credential.
- Host changes invalidate the credential loaded by the previous FreeSWITCH
  process; operators must restart FreeSWITCH after changing the host.
- Upgrading an existing database performs one initial rotation and likewise
  requires a FreeSWITCH restart.
- Traefik, FreeSWITCH, and the firewall agent share the host network namespace.
- The loopback patch must be checked when the pinned FreeSWITCH version changes.
