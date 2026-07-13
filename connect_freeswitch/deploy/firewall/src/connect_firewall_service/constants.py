"""Names and constants shared across the service."""
import ipaddress


# ipset names. Each set exists twice: the base name is the IPv4
# (family inet) set, the "6"-suffixed twin is the IPv6 (family inet6)
# one. Suffixed names stay within the kernel's 31-char ipset name limit.
IPSET_WHITELIST = "connect_fw_whitelist"
IPSET_BLACKLIST = "connect_fw_blacklist"
IPSET_AUTHENTICATED = "connect_fw_authenticated"
IPSET_BANNED = "connect_fw_banned"
IPSET_EXPIRE_SHORT = "connect_fw_expire_short"
IPSET_EXPIRE_LONG = "connect_fw_expire_long"

IPV6_SET_SUFFIX = "6"

# iptables chain
IPTABLES_CHAIN = "connect_fw_voip"

# Hardcoded User-Agent substrings that get the kernel-level string match
# treatment — instant DROP regardless of trust.
UA_BLACKLIST = (
    "VaxSIPUserAgent",
    "friendly-scanner",
    "sipvicious",
    "sipcli",
    "sundayddr",
    "sipsak",
    "sip-scan",
)

# Local networks we never act on — auth events sourced from them are
# treated as harmless development traffic.
PRIVATE_NETWORKS = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("fc00::/7"),
)


def addr_is_private(addr_str: str) -> bool:
    """True if the IP belongs to one of the private ranges above."""
    try:
        addr = ipaddress.ip_address(addr_str)
    except ValueError:
        return False
    return any(addr in net for net in PRIVATE_NETWORKS)
