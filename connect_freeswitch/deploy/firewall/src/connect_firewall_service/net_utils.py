"""IP/CIDR normalization and family routing helpers.

Every value must pass through :func:`normalize_entry` before it reaches
an ``ipset`` invocation. Two reasons:

* the declarative sync in ``ipset_manager.replace_contents`` diffs the
  desired entries against ``ipset list`` output as *strings* — only the
  exact canonical spelling ipset prints back (compressed lowercase
  IPv6, host entries without the /32 or /128 suffix, network address
  instead of a host address inside a CIDR) survives the diff without
  flapping;
* the ipset CLI resolves anything that does not look like an IP via
  DNS, so unvalidated input (e.g. the unban endpoint's path parameter)
  must be rejected before a subprocess is spawned.

IPv4-mapped IPv6 addresses (``::ffff:1.2.3.4``) are unwrapped to plain
IPv4: FreeSWITCH reports them on dual-stack sockets while the packets
flow through the IPv4 netfilter hooks.
"""
from __future__ import annotations

import ipaddress


def normalize_entry(value: str) -> tuple[str, int]:
    """Return ``(canonical_entry, ip_version)`` for an IP or CIDR string.

    Raises ``ValueError`` when the value is not a valid IP or CIDR.
    """
    text = str(value).strip()
    # Unwrap a bare IPv4-mapped IPv6 address before network parsing.
    try:
        addr = ipaddress.ip_address(text)
    except ValueError:
        pass
    else:
        mapped = getattr(addr, "ipv4_mapped", None)
        if mapped is not None:
            addr = mapped
        return str(addr), addr.version
    net = ipaddress.ip_network(text, strict=False)
    if (
        net.version == 6
        and net.prefixlen >= 96
        and net.network_address.ipv4_mapped is not None
        and net.broadcast_address.ipv4_mapped is not None
    ):
        net = ipaddress.ip_network(
            "{}/{}".format(net.network_address.ipv4_mapped, net.prefixlen - 96),
            strict=False,
        )
    if net.prefixlen == net.max_prefixlen:
        return str(net.network_address), net.version
    return str(net), net.version


def set_for(base_name: str, entry: str) -> str:
    """Return the family-specific ipset name for a canonical entry.

    ``entry`` must already be normalized; v4 entries map to
    ``base_name``, v6 entries to ``base_name + "6"``.
    """
    _, version = normalize_entry(entry)
    return base_name if version == 4 else base_name + "6"
