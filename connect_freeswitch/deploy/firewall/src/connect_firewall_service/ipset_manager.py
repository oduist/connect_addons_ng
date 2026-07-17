"""Thin wrapper over the `ipset` CLI.

We shell out instead of using netlink/ipsetpy bindings because:
- ipset CLI is rock solid and present on every Linux distro;
- the operations we need are at most a few per second; the subprocess
  overhead is irrelevant;
- the bindings have surprised us in the reference implementation, the
  CLI never does.
"""
import logging
import re
import subprocess
from typing import Iterable

from .constants import IPV6_SET_SUFFIX

logger = logging.getLogger(__name__)

# Matches ipset save lines like:
# add connect_fw_banned 1.2.3.4 timeout 86400 packets 0 bytes 0 comment "..."
_RE_LIST_ENTRY = re.compile(
    r"^(\S+)"                                   # ip or cidr
    r"(?:\s+timeout\s+(\d+))?"                  # optional timeout
    r"(?:\s+packets\s+\d+\s+bytes\s+\d+)?"      # optional counters
    r'(?:\s+comment\s+"([^"]*)")?'              # optional comment
)


def _run(args: list[str]) -> subprocess.CompletedProcess:
    """Run an ipset command. Stderr is captured for the caller to inspect."""
    return subprocess.run(
        args, check=False, text=True, capture_output=True
    )


def ensure_set(
    name: str,
    *,
    family: str = "inet",
    set_type: str = "hash:ip",
    timeout: int | None = None,
    hashsize: int = 1024,
    maxelem: int = 65536,
) -> None:
    """Create an ipset if it doesn't exist; idempotent via `-exist`."""
    args = [
        "ipset", "create", "-exist", name, set_type,
        "family", family,
        "hashsize", str(hashsize),
        "maxelem", str(maxelem),
        "counters",
        "comment",
    ]
    if timeout is not None:
        args.extend(["timeout", str(timeout)])
    res = _run(args)
    if res.returncode != 0 and "set with the same name already exists" not in res.stderr:
        logger.error("ipset create %s failed: %s", name, res.stderr.strip())


def add_entry(
    name: str, entry: str, *, comment: str | None = None, timeout: int | None = None,
) -> bool:
    args = ["ipset", "add", "-exist", name, entry]
    if timeout is not None:
        args.extend(["timeout", str(timeout)])
    if comment:
        args.extend(["comment", comment])
    res = _run(args)
    if res.returncode != 0:
        logger.warning("ipset add %s %s failed: %s", name, entry, res.stderr.strip())
        return False
    return True


def del_entry(name: str, entry: str) -> bool:
    res = _run(["ipset", "del", "-exist", name, entry])
    if res.returncode != 0:
        logger.warning("ipset del %s %s failed: %s", name, entry, res.stderr.strip())
        return False
    return True


def flush(name: str) -> None:
    _run(["ipset", "flush", name])


def list_entries(name: str) -> list[dict]:
    """Return current entries of the ipset as [{entry, timeout, comment}, ...]."""
    res = _run(["ipset", "list", name])
    if res.returncode != 0:
        if "does not exist" in res.stderr:
            return []
        logger.warning("ipset list %s failed: %s", name, res.stderr.strip())
        return []

    out = []
    in_members = False
    for line in res.stdout.splitlines():
        if line.startswith("Members:"):
            in_members = True
            continue
        if not in_members or not line.strip():
            continue
        m = _RE_LIST_ENTRY.match(line.strip())
        if not m:
            continue
        out.append({
            "entry": m.group(1),
            "timeout": int(m.group(2)) if m.group(2) else None,
            "comment": m.group(3) or "",
        })
    return out


def list_entries_all_families(base_name: str) -> list[dict]:
    """Entries of an IPv4 set and its inet6 twin, tagged with ``family``."""
    out = []
    for suffix, family in (("", 4), (IPV6_SET_SUFFIX, 6)):
        for item in list_entries(base_name + suffix):
            item["family"] = family
            out.append(item)
    return out


def replace_contents(
    name: str,
    desired_entries: Iterable,
) -> tuple[int, int]:
    """Bring the ipset to exactly the desired set of entries.

    Accepts either a flat iterable of IP/CIDR strings or an iterable of
    ``(entry, comment)`` tuples. Returns ``(added, removed)``.

    When comments are supplied we always re-apply them (an ipset add with
    ``-exist`` updates the comment for entries that already exist).
    """
    pairs: list[tuple[str, str]] = []
    for item in desired_entries:
        if isinstance(item, (tuple, list)):
            entry = item[0]
            comment = item[1] if len(item) > 1 else ""
        else:
            entry, comment = item, ""
        pairs.append((str(entry), str(comment or "")))
    desired_map = dict(pairs)
    current = {e["entry"] for e in list_entries(name)}
    desired_set = set(desired_map.keys())
    to_add = desired_set - current
    to_del = current - desired_set
    for entry in to_add:
        add_entry(name, entry, comment=desired_map.get(entry) or None)
    for entry in desired_set & current:
        # Refresh comment for entries that survived — name/note in Odoo
        # may have changed.
        c = desired_map.get(entry)
        if c:
            add_entry(name, entry, comment=c)
    for entry in to_del:
        del_entry(name, entry)
    return len(to_add), len(to_del)


def is_member(name: str, entry: str) -> bool:
    """True if ``entry`` is currently in the ipset."""
    res = _run(["ipset", "test", name, entry])
    # ipset test returns 0 if in set, 1 otherwise; suppress stderr noise.
    return res.returncode == 0
