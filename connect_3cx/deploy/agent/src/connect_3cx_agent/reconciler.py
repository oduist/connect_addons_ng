"""Config pull + participant-state healing.

Two jobs, one debounced loop (the ADR-026 sidecar pattern):

* ``config`` scope — pull /3cx/api/config from Odoo, apply the PBX URL
  and the 3CX API client credentials, persist them to the JSON cache so
  the agent can boot without Odoo next time. A credential change
  invalidates the cached token.
* ``participants`` scope — GET the Call Control full-state dump and
  diff against the local registry: participants the agent tracks but
  the PBX no longer lists get a synthetic ``remove`` (heals events
  missed during WS downtime), so Odoo channels never stay active
  forever.

Triggered on WS reconnect, on /sync from Odoo, and on a periodic
safety-net interval.
"""
from __future__ import annotations

import asyncio
import logging

from .config import (
    AgentSettings,
    runtime_cache_keys,
    save_runtime_cache,
)
from .handler import CallControlHandler
from .odoo_client import OdooClient
from .state import ParticipantRegistry
from .tcx_api import ThreeCXClient

logger = logging.getLogger(__name__)

DEBOUNCE_DELAY = 1.0


def live_participant_entities(state_dump) -> set[str]:
    """Extract participant entity paths from the /callcontrol dump.

    The dump shape is only partially documented; parse defensively:
    a list of DN objects, each carrying its number under ``dn`` (or
    ``number``) and a ``participants`` list of objects with ``id``.
    """
    entities: set[str] = set()
    if not isinstance(state_dump, list):
        return entities
    for item in state_dump:
        if not isinstance(item, dict):
            continue
        dn = item.get("dn") or item.get("number") or ""
        for participant in item.get("participants") or []:
            if not isinstance(participant, dict):
                continue
            pid = participant.get("id")
            if dn and pid is not None:
                entities.add(
                    "/callcontrol/{}/participants/{}".format(dn, pid))
    return entities


class Reconciler:
    def __init__(
        self,
        settings: AgentSettings,
        odoo: OdooClient,
        tcx: ThreeCXClient,
        handler: CallControlHandler,
        registry: ParticipantRegistry,
    ):
        self.settings = settings
        self.odoo = odoo
        self.tcx = tcx
        self.handler = handler
        self.registry = registry
        self._wakeup = asyncio.Event()
        self._scopes: set[str] = set()

    def trigger(self, scope: str = "all") -> None:
        self._scopes.add(scope)
        self._wakeup.set()

    # ------------------------------------------------------------------
    # Scopes
    # ------------------------------------------------------------------

    async def _pull_config(self) -> None:
        config = await self.odoo.get("/3cx/api/config")
        if not isinstance(config, dict):
            return
        creds_changed = False
        for key in ("pbx_url", "client_id", "client_secret"):
            value = config.get(key)
            if value and value != getattr(self.settings, key):
                setattr(self.settings, key, value)
                creds_changed = True
        if "recordings_enabled" in config:
            self.settings.recordings_enabled = bool(
                config["recordings_enabled"])
        if creds_changed:
            self.tcx.invalidate_token()
            logger.info("3CX credentials updated from Odoo config")
        cache = {key: getattr(self.settings, key)
                 for key in runtime_cache_keys()}
        save_runtime_cache(
            self.settings.state_path.replace("state.json", "config.json"),
            cache)

    async def _reconcile_participants(self) -> None:
        if not self.tcx.configured():
            return
        dump = await self.tcx.callcontrol_state()
        live = live_participant_entities(dump)
        stale = self.registry.active_entities() - live
        for entity in stale:
            logger.info("Reconcile: synthetic remove for %s", entity)
            self.handler.emit_synthetic_remove(entity)
        evicted = self.registry.evict_stale()
        if evicted:
            logger.debug("Evicted %d stale participant(s)", evicted)

    # ------------------------------------------------------------------
    # Loop
    # ------------------------------------------------------------------

    async def run_once(self, scopes: set[str]) -> None:
        if scopes & {"config", "all"}:
            try:
                await self._pull_config()
            except Exception as exc:
                logger.warning("Config pull failed: %s", exc)
        if scopes & {"participants", "all"}:
            try:
                await self._reconcile_participants()
            except Exception as exc:
                logger.warning("Participant reconcile failed: %s", exc)

    async def run(self) -> None:
        # Initial config pull so the agent picks up credentials on boot.
        self.trigger("all")
        while True:
            try:
                await asyncio.wait_for(
                    self._wakeup.wait(),
                    timeout=max(15, self.settings.reconcile_interval))
            except asyncio.TimeoutError:
                self._scopes.add("all")
            await asyncio.sleep(DEBOUNCE_DELAY)
            scopes, self._scopes = self._scopes or {"all"}, set()
            self._wakeup.clear()
            await self.run_once(scopes)
