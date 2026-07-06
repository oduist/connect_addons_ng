"""In-memory channel registry.

Tracks live channels by Uniqueid so the agent can:
  * remember MixMonitor recording paths announced via VarSet;
  * know which channels Odoo believes are alive (reconciliation diff);
  * remember pending click-to-call ChannelIds.

The registry is intentionally tiny — no business state, TTL-evicted to
bound memory if Hangup events are ever missed.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class ChannelInfo:
    uniqueid: str
    channel: str = ""
    created_at: float = field(default_factory=time.time)
    recording_path: str = ""
    hung_up: bool = False


class CallState:
    def __init__(self, ttl: int = 21600):
        self.ttl = ttl
        self._channels: dict[str, ChannelInfo] = {}

    def on_event(self, event: dict) -> None:
        name = event.get("Event")
        uniqueid = event.get("Uniqueid", "")
        if not uniqueid:
            return
        if name == "Newchannel":
            self._channels[uniqueid] = ChannelInfo(
                uniqueid=uniqueid, channel=event.get("Channel", ""))
        elif name == "VarSet" and \
                event.get("Variable") == "MIXMONITOR_FILENAME":
            info = self._channels.setdefault(
                uniqueid, ChannelInfo(uniqueid=uniqueid,
                                      channel=event.get("Channel", "")))
            info.recording_path = event.get("Value", "")
        elif name == "Hangup":
            info = self._channels.get(uniqueid)
            if info is not None:
                info.hung_up = True

    def pop_recording(self, uniqueid: str) -> str:
        """Return and clear the recording path of a hung-up channel."""
        info = self._channels.get(uniqueid)
        if info is None or not info.recording_path:
            return ""
        path, info.recording_path = info.recording_path, ""
        return path

    def forget(self, uniqueid: str) -> None:
        self._channels.pop(uniqueid, None)

    def active_uniqueids(self) -> set[str]:
        return {uid for uid, info in self._channels.items()
                if not info.hung_up}

    def get(self, uniqueid: str) -> ChannelInfo | None:
        return self._channels.get(uniqueid)

    def evict_stale(self) -> int:
        """Drop hung-up and TTL-expired entries; return how many."""
        now = time.time()
        stale = [
            uid for uid, info in self._channels.items()
            if (info.hung_up and not info.recording_path)
            or now - info.created_at > self.ttl
        ]
        for uid in stale:
            del self._channels[uid]
        return len(stale)
