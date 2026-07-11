"""Config pull + channel-state healing.

Two jobs, one debounced loop (the firewall service pattern):

* ``config`` scope — pull /asterisk/api/config from Odoo, apply AMI
  credentials / event filter, persist them to the JSON cache so the
  agent can boot without Odoo next time.
* ``channels`` scope — run ``CoreShowChannels`` and diff against the
  local registry: channels the agent tracks but Asterisk no longer
  lists get a synthetic ``Hangup`` (heals events missed during AMI
  downtime), so Odoo channels never stay active forever.

Triggered on AMI reconnect, on /sync from Odoo, and on a periodic
safety-net interval.
"""
from __future__ import annotations

import asyncio
import logging
import time

from .ami import AMIClient
from .ami_handler import AMIHandler
from .call_state import CallState
from .config import (
    AgentSettings,
    apply_cache_to_settings,
    runtime_cache_keys,
    save_runtime_cache,
)
from .odoo_client import OdooClient

logger = logging.getLogger(__name__)

DEBOUNCE_DELAY = 1.0


class Reconciler:
    def __init__(
        self,
        settings: AgentSettings,
        odoo: OdooClient,
        ami: AMIClient,
        handler: AMIHandler,
        call_state: CallState,
    ):
        self.settings = settings
        self.odoo = odoo
        self.ami = ami
        self.handler = handler
        self.call_state = call_state
        self._wakeup = asyncio.Event()
        self._scopes: set[str] = set()

    def trigger(self, scope: str = "all") -> None:
        self._scopes.add(scope)
        self._wakeup.set()

    # ------------------------------------------------------------------
    # Scopes
    # ------------------------------------------------------------------

    async def _pull_config(self) -> None:
        config = await self.odoo.get("/asterisk/api/config")
        if not isinstance(config, dict):
            return
        ami = config.get("ami") or {}
        cache = {
            "ami_host": ami.get("host") or self.settings.ami_host,
            "ami_port": int(ami.get("port") or self.settings.ami_port),
            "ami_user": ami.get("user") or self.settings.ami_user,
            "ami_password": ami.get("password")
                            or self.settings.ami_password,
            "events": ",".join(config.get("events") or []),
            "recordings_enabled": bool(
                config.get("recordings_enabled", True)),
        }
        changed = any(
            getattr(self.settings, key, None) != value
            for key, value in cache.items()
        )
        apply_cache_to_settings(self.settings, cache)
        save_runtime_cache(
            self.settings.state_path.replace("state.json", "config.json"),
            {key: getattr(self.settings, key)
             for key in runtime_cache_keys()})
        if config.get("events"):
            self.handler.set_events(config["events"])
        if changed:
            logger.info("Runtime config updated from Odoo; "
                        "resetting AMI connection")
            self.ami.host = self.settings.ami_host
            self.ami.port = self.settings.ami_port
            self.ami.username = self.settings.ami_user
            self.ami.secret = self.settings.ami_password
            await self.ami.close()

    async def _reconcile_channels(self) -> None:
        if not self.ami.is_connected:
            return
        events = await self.ami.action(
            {"Action": "CoreShowChannels"}, timeout=15, collect_events=True)
        alive = {event.get("Uniqueid") for event in events
                 if event.get("Uniqueid")}
        tracked = self.call_state.active_uniqueids()
        for uniqueid in tracked - alive:
            info = self.call_state.get(uniqueid)
            logger.info("Reconcile: emitting synthetic Hangup for %s (%s)",
                        uniqueid, info.channel if info else "?")
            self.handler.handle({
                "Event": "Hangup",
                "Uniqueid": uniqueid,
                "Linkedid": uniqueid,
                "Channel": info.channel if info else "",
                "Cause": "16",
                "Cause-txt": "agent-reconciled",
                "ChannelStateDesc": "Unknown",
            })
            self.call_state.forget(uniqueid)
        evicted = self.call_state.evict_stale()
        if evicted:
            logger.debug("Evicted %d stale channel entries", evicted)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self) -> None:
        self.trigger("all")
        last_periodic = 0.0
        while True:
            try:
                await asyncio.wait_for(
                    self._wakeup.wait(),
                    timeout=max(15, self.settings.reconcile_interval))
            except asyncio.TimeoutError:
                pass
            await asyncio.sleep(DEBOUNCE_DELAY)
            scopes, self._scopes = self._scopes, set()
            self._wakeup.clear()
            if not scopes:
                # Periodic safety net.
                if time.time() - last_periodic >= \
                        self.settings.reconcile_interval:
                    scopes = {"channels"}
                else:
                    continue
            if scopes & {"all", "config"}:
                try:
                    await self._pull_config()
                except Exception as exc:
                    logger.warning("Config pull failed: %s", exc)
            if scopes & {"all", "channels"}:
                try:
                    await self._reconcile_channels()
                    last_periodic = time.time()
                except Exception as exc:
                    logger.warning("Channel reconciliation failed: %s", exc)
