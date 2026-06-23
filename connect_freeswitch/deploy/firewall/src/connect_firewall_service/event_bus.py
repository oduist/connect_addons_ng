"""In-memory event bus shared by the ESL handler and the SSE endpoint.

Holds a ring buffer of the last N events for new dashboard tabs and a
set of subscriber queues for live updates. Also tracks lightweight
counters used by the sparkline and top-IPs widgets — no SQLite, no
external store; everything resets on service restart.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from typing import AsyncIterator, Deque

RING_SIZE = 1000
ATTEMPT_WINDOW_SEC = 3600    # 1 hour for the sparkline
TOP_IP_WINDOW_SEC = 86400    # 24 hours for top-IPs


class EventBus:
    def __init__(self) -> None:
        self._ring: Deque[dict] = deque(maxlen=RING_SIZE)
        self._subscribers: set[asyncio.Queue[dict]] = set()
        # (ip, ts) tuples — drained lazily; cheap to keep linearly.
        self._attempts: Deque[tuple[str, float]] = deque()
        self._ip_hits: Deque[tuple[str, float]] = deque()

    # ------------------------------------------------------------------
    # Producer side — ESL handler / Reconciler call this
    # ------------------------------------------------------------------

    def record(self, event: dict) -> None:
        """Push an event into the ring + broadcast it to subscribers.

        Expected shape: ``{"type": "ban"|"unban"|"auth"|...,
        "ip": "...", "ts": float, ...other fields...}``.
        """
        if "ts" not in event:
            event = {**event, "ts": time.time()}
        self._ring.append(event)
        ts = event["ts"]
        ip = event.get("ip")
        if ip and event.get("type") in ("auth_fail", "auto_ban", "auth_success"):
            self._attempts.append((ip, ts))
            self._ip_hits.append((ip, ts))
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Slow consumer — drop the oldest queued event.
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    pass

    # ------------------------------------------------------------------
    # Consumer side — HTTP server reads from here
    # ------------------------------------------------------------------

    def recent(self, limit: int = 100) -> list[dict]:
        if limit >= len(self._ring):
            return list(self._ring)
        return list(self._ring)[-limit:]

    async def subscribe(self) -> AsyncIterator[dict]:
        """Async iterator that yields new events forever.

        The first message is a snapshot of the ring so the client can
        backfill its UI; afterwards each new ``record(...)`` is pushed.
        """
        q: asyncio.Queue[dict] = asyncio.Queue(maxsize=256)
        self._subscribers.add(q)
        try:
            # Backfill snapshot.
            for event in self.recent(50):
                yield event
            while True:
                event = await q.get()
                yield event
        finally:
            self._subscribers.discard(q)

    # ------------------------------------------------------------------
    # Aggregations consumed by the sparkline / top-IPs widgets
    # ------------------------------------------------------------------

    def _drain(self, dq: Deque[tuple[str, float]], window: float) -> None:
        cutoff = time.time() - window
        while dq and dq[0][1] < cutoff:
            dq.popleft()

    def attempts_per_minute(self) -> list[dict]:
        """Buckets for the last hour: 60 entries, oldest first."""
        self._drain(self._attempts, ATTEMPT_WINDOW_SEC)
        now = time.time()
        buckets = [0] * 60
        for _ip, ts in self._attempts:
            slot = int((now - ts) // 60)
            if 0 <= slot < 60:
                buckets[59 - slot] += 1
        return [{"minute": i, "count": v} for i, v in enumerate(buckets)]

    def top_ips(self, n: int = 10) -> list[dict]:
        """Top-N IPs by hit count over the last 24h."""
        self._drain(self._ip_hits, TOP_IP_WINDOW_SEC)
        counts: dict[str, int] = defaultdict(int)
        for ip, _ in self._ip_hits:
            counts[ip] += 1
        ranked = sorted(counts.items(), key=lambda kv: -kv[1])[:n]
        return [{"ip": ip, "count": c} for ip, c in ranked]
