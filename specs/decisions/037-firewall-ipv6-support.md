# ADR-037: IPv6 support in the FreeSWITCH firewall service

**Status:** Accepted
**Date:** 2026-07-12

## Context

ADR-014 shipped the FreeSWITCH firewall service (`oduist/freeswitch-firewall`)
as explicitly IPv4-only, with the extension path already sketched: "a parallel
`ip6tables` chain and `family inet6` ipsets can be layered in without changing
the model". GitHub issue #70 asks for that extension.

Today the IPv4-only assumption lives in four places:

1. all six ipsets are created with the default `family inet`
   (`ipset_manager.ensure_set`, `__main__.install_firewall_baseline`);
2. the `connect_fw_voip` chain exists only in `iptables` — IPv6 SIP traffic
   bypasses the firewall entirely;
3. the ESL IP-extraction regexes in `esl_handler.py` match dotted-quad only,
   so IPv6 attackers are invisible to auto-ban/trust;
4. `PRIVATE_NETWORKS` lists only IPv4 ranges.

Meanwhile the Odoo-side validator (`ipaddress.ip_network(strict=False)`)
already accepts IPv6 whitelist/blacklist entries — they are stored but the
service's `ipset add` into an `inet` set fails silently. Worse, a related
IPv4 bug exists today: `ipset_manager.replace_contents` diffs *strings*, and a
non-canonical Odoo entry (e.g. `1.2.3.4/24`, which ipset canonicalizes to
`1.2.3.0/24`) is added and then deleted in the same reconcile pass — the entry
is effectively absent from the kernel and flaps on every sync.

## Options

1. **Parallel `inet6` ipsets + `ip6tables` chain** — the path ADR-014
   anticipated. Same model, same chain logic, one more binary.
2. **Rewrite on nftables** — a single `inet` family table covers both
   protocols natively. Rejected: ADR-014 deliberately chose iptables+ipset
   (rock-solid CLI, years of production use in the Asterisk reference);
   a data-plane rewrite is out of proportion for this feature and would
   invalidate operational knowledge (docs, troubleshooting, dashboards).
3. **Do nothing / reject IPv6 in Odoo validation** — hides the gap instead of
   closing it; SIP over IPv6 is increasingly common on public VPS hosts.

## Decision

Option 1 — layer IPv6 in as parallel structures, keeping the six-set model
per family.

### Parallel inet6 sets and chain

Six new ipsets named by suffixing `6` (`connect_fw_whitelist6`,
`connect_fw_blacklist6`, `connect_fw_authenticated6`, `connect_fw_banned6`,
`connect_fw_expire_short6`, `connect_fw_expire_long6` — all within the 31-char
ipset name limit), `family inet6`, same types/timeouts as their v4 twins.
The same `connect_fw_voip` chain is built in `ip6tables` with the same
port hooks, the same set-match order and the same kernel UA string filter.
`iptables_manager` is parameterized over a `(binary, sets)` family table;
public signatures (`apply_baseline(tcp_ports, udp_ports)`, `teardown`) are
unchanged.

### Canonical normalization as an ipset-call invariant

Every IP/CIDR is normalized before *any* ipset invocation to exactly the form
`ipset list` prints back: compressed lowercase IPv6, host entries without the
`/32` / `/128` suffix, IPv4-mapped IPv6 (`::ffff:1.2.3.4`) unwrapped to plain
IPv4. A new `net_utils.py` owns `normalize_entry()` (returns the canonical
string + IP version) and `set_for()` (routes an entry to the v4 or v6 set).
This:

- fixes the pre-existing IPv4 `replace_contents` churn bug described above;
- makes the string-diff sync semantics of ADR-014 correct for IPv6, where
  many textual spellings map to one kernel entry;
- protects against the ipset CLI's DNS resolution of non-IP-looking input
  (the unban HTTP endpoint passes a user-supplied path segment) — anything
  that does not parse is rejected before a subprocess is spawned;
- keeps dual-stack sockets sane: an IPv4-mapped source reported by
  FreeSWITCH is banned where the packets actually flow (the v4 chain).

The Odoo models apply the same normalization on create/write and compare
duplicates on normalized values. No data migration: legacy rows are
normalized by the service on every sync regardless of stored spelling; a
legacy row like `1.2.3.4/24` will display as `1.2.3.0/24` after its next
write, which is semantically identical under `strict=False`.

### Graceful degradation instead of a feature flag

No new Odoo setting. At baseline install the service probes `ip6tables`;
when the binary is missing or the kernel has IPv6 disabled
(`ipv6.disable=1`), the v6 family is skipped with an error log and the
service keeps protecting IPv4 exactly as before. The Dockerfile asserts at
build time that the Alpine `iptables` package still ships `ip6tables`.

### ESL extraction becomes family-agnostic

`_extract_ip` tries `ipaddress.ip_address()` on bare header values first,
then falls back to regex candidates (dotted-quad, `received=` with optional
brackets, bracketed IPv6 URI host), each validated by parsing before use, and
returns the normalized form. `PRIVATE_NETWORKS` additionally ignores `::1/128`,
`fe80::/10` and `fc00::/7` sources.

### API surface

The dashboard/JSON endpoints (`/firewall/api/bans` etc.) return the merged
v4+v6 entries in the existing `{entry, timeout, comment}` shape plus a new
`family` field; the Lit dashboard renders entries as opaque strings and needs
no changes. `DELETE /firewall/api/bans/{ip}` normalizes its input and deletes
from the set of the matching family. Heartbeat counts sum both families.

## Consequences

- IPv6 SIP endpoints get the same challenge-window protection, whitelisting
  and manual bans as IPv4; hosts without IPv6 see no behavioral change.
- Twelve ipsets instead of six; `docs/admin/firewall.md` troubleshooting now
  covers `ip6tables`/`*6` sets and the `ip6_tables`/`ip6table_filter` kernel
  modules.
- The whitelist/blacklist sync flap for non-canonical IPv4 CIDRs is fixed as
  a side effect.
- Firewall service `1.2.0`, image `oduist/freeswitch-firewall:2.1.0`
  (tag = short module manifest version per the deploy-image policy),
  module `19.0.2.1.0`.
- Enabling IPv6 sofia profiles in the shipped FreeSWITCH image config stays
  out of scope — deployment-specific; the kernel-level protection of the SIP
  ports works regardless of whether FreeSWITCH listens on v6 yet.

## References

- GitHub issue #70 — feature request.
- ADR-014 `freeswitch-firewall-service.md` — base architecture; its
  "IPv4 only" subsection is superseded by this ADR.
- ADR-015 `firewall-token-controllers.md` — control-plane auth (unchanged).
