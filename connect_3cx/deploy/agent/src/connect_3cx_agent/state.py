"""In-memory participant registry.

Tracks live Call Control participants by entity path so the agent can:
  * emit the last-known state with Remove events (the WS Remove payload
    only names the entity — 3CX no longer serves it);
  * stamp the answer time when a participant turns Connected;
  * diff against the PBX full-state dump (reconciliation).

The registry is intentionally tiny — no business state, TTL-evicted to
bound memory if Remove events are ever missed.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class ParticipantInfo:
    entity: str
    dn: str = ""
    participant_id: str = ""
    state: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    answered_at: float | None = None


class ParticipantRegistry:
    def __init__(self, ttl: int = 21600):
        self.ttl = ttl
        self._participants: dict[str, ParticipantInfo] = {}

    def on_upsert(self, entity: str, dn: str, participant_id: str,
                  state: dict) -> ParticipantInfo:
        info = self._participants.get(entity)
        if info is None:
            info = ParticipantInfo(
                entity=entity, dn=dn, participant_id=participant_id)
            self._participants[entity] = info
        info.state = state or {}
        if info.answered_at is None and \
                (state or {}).get("status") == "Connected":
            info.answered_at = time.time()
        return info

    def pop(self, entity: str) -> ParticipantInfo | None:
        return self._participants.pop(entity, None)

    def get(self, entity: str) -> ParticipantInfo | None:
        return self._participants.get(entity)

    def active_entities(self) -> set[str]:
        return set(self._participants)

    def evict_stale(self) -> int:
        """Drop TTL-expired entries; return how many."""
        now = time.time()
        stale = [
            entity for entity, info in self._participants.items()
            if now - info.created_at > self.ttl
        ]
        for entity in stale:
            del self._participants[entity]
        return len(stale)
