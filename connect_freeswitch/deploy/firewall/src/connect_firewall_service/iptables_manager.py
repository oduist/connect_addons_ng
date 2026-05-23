"""Build and reset the `connect_fw_voip` iptables chain.

The chain evaluates the six ipsets in order plus kernel-level User-Agent
string matches, then defaults to ACCEPT. The whole bring-up is idempotent
— we drop our old INPUT references first, flush the chain (creating it if
needed) and re-add everything.
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
    UA_BLACKLIST,
)

logger = logging.getLogger(__name__)


def _run(args: list[str], *, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=check, text=True, capture_output=True)


def _detach_input(tcp_ports: str, udp_ports: str) -> None:
    """Remove our jump rules from INPUT, ignoring 'no such rule' errors."""
    for proto, ports in (("tcp", tcp_ports), ("udp", udp_ports)):
        if not ports:
            continue
        _run([
            "iptables", "-D", "INPUT",
            "-p", proto, "-m", "multiport", "--dports", ports,
            "-j", IPTABLES_CHAIN,
        ])


def _ensure_chain() -> None:
    """Create the chain or flush it if it already exists."""
    res = _run(["iptables", "-F", IPTABLES_CHAIN])
    if res.returncode != 0:
        # Chain probably doesn't exist yet.
        _run(["iptables", "-N", IPTABLES_CHAIN], check=False)


def _attach_input(tcp_ports: str, udp_ports: str) -> None:
    for proto, ports in (("tcp", tcp_ports), ("udp", udp_ports)):
        if not ports:
            continue
        _run([
            "iptables", "-I", "INPUT",
            "-p", proto, "-m", "multiport", "--dports", ports,
            "-j", IPTABLES_CHAIN,
        ])


def _populate_chain() -> None:
    """Fill the chain with the policy rules in order."""
    set_rules = [
        (IPSET_WHITELIST, "ACCEPT"),
        (IPSET_BLACKLIST, "DROP"),
        (IPSET_AUTHENTICATED, "ACCEPT"),
        (IPSET_BANNED, "DROP"),
        (IPSET_EXPIRE_SHORT, "ACCEPT"),
        (IPSET_EXPIRE_LONG, "DROP"),
    ]
    for set_name, target in set_rules:
        _run([
            "iptables", "-A", IPTABLES_CHAIN,
            "-m", "set", "--match-set", set_name, "src",
            "-j", target,
        ])
    for ua in UA_BLACKLIST:
        _run([
            "iptables", "-A", IPTABLES_CHAIN,
            "-m", "string", "--string", ua,
            "--algo", "bm", "--to", "65535",
            "-j", "DROP",
        ])
    _run(["iptables", "-A", IPTABLES_CHAIN, "-j", "ACCEPT"])


def apply_baseline(tcp_ports: str, udp_ports: str) -> None:
    """Idempotently install (or re-install) the chain and its INPUT hooks."""
    _detach_input(tcp_ports, udp_ports)
    _ensure_chain()
    _populate_chain()
    _attach_input(tcp_ports, udp_ports)
    logger.info(
        "iptables chain %s installed (tcp=%s udp=%s)",
        IPTABLES_CHAIN, tcp_ports, udp_ports,
    )


def teardown(tcp_ports: str, udp_ports: str) -> None:
    """Remove the chain and our INPUT references (intended for shutdown)."""
    _detach_input(tcp_ports, udp_ports)
    _run(["iptables", "-F", IPTABLES_CHAIN])
    _run(["iptables", "-X", IPTABLES_CHAIN])
