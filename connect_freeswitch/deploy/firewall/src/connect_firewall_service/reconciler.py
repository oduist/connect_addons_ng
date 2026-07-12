"""Reconciler — pulls desired state from Odoo and applies it to ipsets.

Triggered by:
  * the HTTP endpoint ``/firewall/sync`` (Odoo postcommit hook);
  * its own internal timer every ``RECONCILE_INTERVAL`` seconds (safety
    net for missed POSTs).

A short debounce window collapses bursts of POSTs into a single Odoo
fetch.
"""
from __future__ import annotations

import asyncio
import logging
import time

from . import ipset_manager
from .config import (
    ServiceSettings,
    runtime_cache_keys,
    save_runtime_cache,
)
from .constants import IPSET_BLACKLIST, IPSET_WHITELIST, IPV6_SET_SUFFIX
from .net_utils import normalize_entry
from .odoo_client import OdooClient

logger = logging.getLogger(__name__)

DEBOUNCE_SECONDS = 1.0
RECONCILE_INTERVAL = 300.0  # 5 minutes safety net


def _format_comment(record: dict) -> str:
    """Build the ipset comment shown in the dashboard from a whitelist /
    blacklist record fetched from Odoo (uses ``name`` plus optional
    ``note``)."""
    parts = [str(record.get("name") or "").strip()]
    note = str(record.get("note") or "").strip()
    if note:
        parts.append(note)
    # ipset comments cap at 255 chars; ipset rejects newlines.
    text = " — ".join(p for p in parts if p)
    return text.replace("\n", " ")[:255]


def _split_by_family(rows: list) -> tuple[list, list]:
    """Turn Odoo whitelist/blacklist rows into per-family (entry, comment)
    pairs, normalized to ipset's canonical spelling. Rows that don't
    parse as an IP or CIDR are skipped with a warning."""
    v4, v6 = [], []
    for record in rows:
        raw = record.get("ip_or_cidr")
        try:
            entry, version = normalize_entry(raw)
        except (TypeError, ValueError):
            logger.warning("Skipping invalid list entry from Odoo: %r", raw)
            continue
        (v4 if version == 4 else v6).append((entry, _format_comment(record)))
    return v4, v6


def _sync_list(base_set: str, rows: list) -> tuple[int, int]:
    """Reconcile both family sets of a whitelist/blacklist pair."""
    v4, v6 = _split_by_family(rows)
    a4, r4 = ipset_manager.replace_contents(base_set, v4)
    a6, r6 = ipset_manager.replace_contents(base_set + IPV6_SET_SUFFIX, v6)
    return a4 + a6, r4 + r6


class Reconciler:
    def __init__(self, settings: ServiceSettings, odoo: OdooClient):
        self.settings = settings
        self.odoo = odoo
        self._event = asyncio.Event()
        self._pending_scope = "all"
        self.last_sync_at: float | None = None
        self.last_sync_scope: str | None = None
        self.last_sync_error: str | None = None

    def trigger(self, scope: str = "all") -> None:
        """Wake the reconciler to sync the given scope soon."""
        self._pending_scope = scope
        self._event.set()

    async def _apply_settings(self, cfg: dict) -> None:
        changed = False
        for key in runtime_cache_keys():
            if key not in cfg or cfg[key] is None:
                continue
            value = cfg[key]
            current = getattr(self.settings, key, None)
            if isinstance(current, bool):
                value = bool(value)
            elif isinstance(current, int):
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    continue
            if value != current:
                setattr(self.settings, key, value)
                changed = True
        if changed:
            save_runtime_cache(
                self.settings.config_cache_path,
                {k: getattr(self.settings, k) for k in runtime_cache_keys()},
            )

    async def _sync_once(self, scope: str) -> None:
        if scope in ("all", "settings"):
            cfg = await self.odoo.get("/config")
            if isinstance(cfg, dict):
                await self._apply_settings(cfg)
        if scope in ("all", "whitelist"):
            wl = await self.odoo.get("/whitelist") or []
            added, removed = _sync_list(IPSET_WHITELIST, wl)
            logger.info("whitelist sync: +%s -%s", added, removed)
        if scope in ("all", "blacklist"):
            bl = await self.odoo.get("/blacklist") or []
            added, removed = _sync_list(IPSET_BLACKLIST, bl)
            logger.info("blacklist sync: +%s -%s", added, removed)

    async def run(self) -> None:
        """Reconciler main loop — periodic + on-demand syncs."""
        while True:
            try:
                await asyncio.wait_for(self._event.wait(), timeout=RECONCILE_INTERVAL)
                scope = self._pending_scope
                self._event.clear()
                # Debounce bursts.
                await asyncio.sleep(DEBOUNCE_SECONDS)
                # If more triggers arrived during the debounce, fold them in.
                if self._event.is_set():
                    # Any mix of scopes upgrades to "all" — it's cheap and
                    # avoids the bug where two different scopes inside the
                    # debounce window would silently keep only the first.
                    if scope != self._pending_scope:
                        scope = "all"
                    self._event.clear()
            except asyncio.TimeoutError:
                scope = "all"
            try:
                await self._sync_once(scope)
                self.last_sync_at = time.time()
                self.last_sync_scope = scope
                self.last_sync_error = None
                logger.debug("Reconciler sync done (scope=%s)", scope)
            except Exception as exc:
                self.last_sync_error = str(exc)
                logger.warning("Reconciler sync failed: %s", exc)
