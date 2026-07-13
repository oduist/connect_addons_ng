"""Build and reset the `connect_fw_voip` iptables/ip6tables chains.

Each address family gets its own copy of the chain: `iptables` matches
the base-named ipsets, `ip6tables` matches their "6"-suffixed inet6
twins. The chain evaluates the six ipsets in order plus kernel-level
User-Agent string matches, then defaults to ACCEPT. The whole bring-up
is idempotent — we drop our old INPUT references first, flush the chain
(creating it if needed) and re-add everything.

When ip6tables is unavailable (missing binary, or a kernel booted with
ipv6.disable=1) the IPv6 family is skipped with an error log and the
service keeps protecting IPv4 — no configuration flag involved.
"""
import logging
import subprocess

from .constants import (
    IPSET_AUTHENTICATED,
    IPSET_BANNED,
    IPSET_BLACKLIST,
    IPSET_EXPIRE_LONG,
    IPSET_EXPIRE_SHORT,
    IPSET_WHITELIST,
    IPTABLES_CHAIN,
    IPV6_SET_SUFFIX,
    UA_BLACKLIST,
)

logger = logging.getLogger(__name__)

# Evaluation order of the ipsets inside the chain (base names; the
# ip6tables copy appends IPV6_SET_SUFFIX to each).
_SET_RULES = (
    (IPSET_WHITELIST, "ACCEPT"),
    (IPSET_BLACKLIST, "DROP"),
    (IPSET_AUTHENTICATED, "ACCEPT"),
    (IPSET_BANNED, "DROP"),
    (IPSET_EXPIRE_SHORT, "ACCEPT"),
    (IPSET_EXPIRE_LONG, "DROP"),
)

# (binary, ipset name suffix) per address family.
FAMILIES = (
    ("iptables", ""),
    ("ip6tables", IPV6_SET_SUFFIX),
)


def _run(args: list[str], *, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=check, text=True, capture_output=True)


def _family_available(binary: str) -> bool:
    """True when the binary exists and the kernel accepts its table."""
    try:
        res = _run([binary, "-L", "INPUT", "-n"])
    except FileNotFoundError:
        logger.error("%s binary not found — skipping this address family", binary)
        return False
    if res.returncode != 0:
        logger.error(
            "%s unusable (%s) — skipping this address family",
            binary, res.stderr.strip(),
        )
        return False
    return True


def _detach_input(binary: str, tcp_ports: str, udp_ports: str) -> None:
    """Remove our jump rules from INPUT, ignoring 'no such rule' errors."""
    for proto, ports in (("tcp", tcp_ports), ("udp", udp_ports)):
        if not ports:
            continue
        _run([
            binary, "-D", "INPUT",
            "-p", proto, "-m", "multiport", "--dports", ports,
            "-j", IPTABLES_CHAIN,
        ])


def _ensure_chain(binary: str) -> None:
    """Create the chain or flush it if it already exists."""
    res = _run([binary, "-F", IPTABLES_CHAIN])
    if res.returncode != 0:
        # Chain probably doesn't exist yet.
        _run([binary, "-N", IPTABLES_CHAIN], check=False)


def _attach_input(binary: str, tcp_ports: str, udp_ports: str) -> None:
    for proto, ports in (("tcp", tcp_ports), ("udp", udp_ports)):
        if not ports:
            continue
        _run([
            binary, "-I", "INPUT",
            "-p", proto, "-m", "multiport", "--dports", ports,
            "-j", IPTABLES_CHAIN,
        ])


def _populate_chain(binary: str, set_suffix: str) -> None:
    """Fill the chain with the policy rules in order."""
    for set_name, target in _SET_RULES:
        _run([
            binary, "-A", IPTABLES_CHAIN,
            "-m", "set", "--match-set", set_name + set_suffix, "src",
            "-j", target,
        ])
    for ua in UA_BLACKLIST:
        _run([
            binary, "-A", IPTABLES_CHAIN,
            "-m", "string", "--string", ua,
            "--algo", "bm", "--to", "65535",
            "-j", "DROP",
        ])
    _run([binary, "-A", IPTABLES_CHAIN, "-j", "ACCEPT"])


def apply_baseline(tcp_ports: str, udp_ports: str) -> None:
    """Idempotently install (or re-install) both chains and INPUT hooks."""
    for binary, set_suffix in FAMILIES:
        if not _family_available(binary):
            continue
        _detach_input(binary, tcp_ports, udp_ports)
        _ensure_chain(binary)
        _populate_chain(binary, set_suffix)
        _attach_input(binary, tcp_ports, udp_ports)
        logger.info(
            "%s chain %s installed (tcp=%s udp=%s)",
            binary, IPTABLES_CHAIN, tcp_ports, udp_ports,
        )


def teardown(tcp_ports: str, udp_ports: str) -> None:
    """Remove the chains and our INPUT references (intended for shutdown)."""
    for binary, _set_suffix in FAMILIES:
        if not _family_available(binary):
            continue
        _detach_input(binary, tcp_ports, udp_ports)
        _run([binary, "-F", IPTABLES_CHAIN])
        _run([binary, "-X", IPTABLES_CHAIN])
