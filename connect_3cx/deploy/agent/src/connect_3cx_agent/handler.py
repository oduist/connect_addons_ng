"""Call Control WS message handling and event normalization.

The WS delivers ``{"sequence": N, "event": {"event_type": T, "entity":
"/callcontrol/...", "attached_data": ...}}`` where event_type is
0=Upsert, 1=Remove, 2=DTMFstring, 3=PromptPlaybackFinished,
4=Response. Only participant entities are interesting: on Upsert the
agent re-GETs the entity (the WS payload carries no state) and stores
it in the registry; on Remove it emits the registry's last-known state.

Normalized events POSTed to Odoo ``/3cx/webhook/events``:

    {"event": "upsert"|"remove", "entity": "...", "dn": "101",
     "participant_id": "5", "ts": <epoch float>,
     "answered_at": <epoch float or None>,
     "state": {<participant object as served by the PBX>}}
"""
from __future__ import annotations

import logging
import re
import time

from .odoo_client import OdooClient
from .state import ParticipantInfo, ParticipantRegistry
from .tcx_api import ThreeCXClient

logger = logging.getLogger(__name__)

EVENT_UPSERT = 0
EVENT_REMOVE = 1

RE_PARTICIPANT = re.compile(
    r"^callcontrol/(?P<dn>[^/]+)/participants/(?P<pid>\d+)$")


def parse_participant_entity(entity: str) -> tuple[str, str] | None:
    """Return (dn, participant_id) for a participant entity path."""
    if not isinstance(entity, str):
        return None
    match = RE_PARTICIPANT.match(entity.strip("/"))
    if match is None:
        return None
    return match.group("dn"), match.group("pid")


class CallControlHandler:
    def __init__(self, tcx: ThreeCXClient, odoo: OdooClient,
                 registry: ParticipantRegistry):
        self.tcx = tcx
        self.odoo = odoo
        self.registry = registry
        self.forwarded_count = 0
        self.dropped_count = 0

    async def handle_message(self, message: dict) -> None:
        """Process one decoded WS message."""
        event = (message or {}).get("event") or {}
        event_type = event.get("event_type")
        entity = event.get("entity") or ""
        parsed = parse_participant_entity(entity)
        if parsed is None:
            # DN/device-level updates, DTMF, WS responses — not ledger
            # material.
            self.dropped_count += 1
            return
        dn, pid = parsed
        if event_type == EVENT_UPSERT:
            await self._on_upsert(entity, dn, pid)
        elif event_type == EVENT_REMOVE:
            self._on_remove(entity, dn, pid)
        else:
            self.dropped_count += 1

    async def _on_upsert(self, entity: str, dn: str, pid: str) -> None:
        try:
            state = await self.tcx.get_entity(entity)
        except Exception as exc:
            # The participant may already be gone (fast calls): keep the
            # last known state if any, otherwise drop — the reconciler
            # will heal.
            logger.debug("Entity fetch failed for %s: %s", entity, exc)
            state = None
        if not isinstance(state, dict):
            info = self.registry.get(entity)
            if info is None:
                self.dropped_count += 1
                return
            state = info.state
        info = self.registry.on_upsert(entity, dn, pid, state)
        self._emit("upsert", info)

    def _on_remove(self, entity: str, dn: str, pid: str) -> None:
        info = self.registry.pop(entity)
        if info is None:
            info = ParticipantInfo(entity=entity, dn=dn,
                                   participant_id=pid)
        self._emit("remove", info)

    def emit_synthetic_remove(self, entity: str) -> None:
        """Reconciler path: the PBX no longer lists this participant."""
        parsed = parse_participant_entity(entity)
        dn, pid = parsed if parsed else ("", "")
        self._on_remove(entity, dn, pid)

    def _emit(self, kind: str, info: ParticipantInfo) -> None:
        self.odoo.enqueue_event({
            "event": kind,
            "entity": info.entity,
            "dn": info.dn,
            "participant_id": info.participant_id,
            "ts": time.time(),
            "answered_at": info.answered_at,
            "state": info.state or {},
        })
        self.forwarded_count += 1
