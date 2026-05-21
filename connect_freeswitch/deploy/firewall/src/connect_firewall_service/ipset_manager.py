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


def replace_contents(name: str, desired_entries: Iterable[str]) -> tuple[int, int]:
    """Bring the ipset to exactly the desired set of entries.

    Returns (added, removed). Timeouts/comments on existing entries are
    untouched — only the set membership is reconciled.
    """
    current = {e["entry"] for e in list_entries(name)}
    desired = set(desired_entries)
    to_add = desired - current
    to_del = current - desired
    for entry in to_add:
        add_entry(name, entry)
    for entry in to_del:
        del_entry(name, entry)
    return len(to_add), len(to_del)
