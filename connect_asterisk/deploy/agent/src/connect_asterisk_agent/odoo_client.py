"""HTTP client for the paired Odoo + a batched event outbox.

Talks to /asterisk/webhook/* and /asterisk/api/* on Odoo, authenticated
with the shared ``asterisk_agent_token`` carried as ``Authorization:
Bearer <token>``. Events are batched (size/time window) into single
POSTs; when Odoo is down the queue grows in memory and the reconciler
heals whatever overflows.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OUTBOX_MAX = 10000
SEND_FAIL_DELAY = 5.0
REQUEST_TIMEOUT = 15.0


class OdooClient:
    def __init__(self, base_url: str, token: str,
                 batch_size: int = 50, batch_window: float = 0.2):
        self.base = base_url.rstrip("/")
        self.token = token
        self.batch_size = batch_size
        self.batch_window = batch_window
        self._http: httpx.AsyncClient | None = None
        self._outbox: asyncio.Queue[dict] = asyncio.Queue(maxsize=OUTBOX_MAX)
        self.last_call_ok: bool = False

    # ------------------------------------------------------------------
    # HTTP plumbing
    # ------------------------------------------------------------------

    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=self.base,
                headers={"Authorization": "Bearer " + self.token},
                timeout=REQUEST_TIMEOUT,
            )
        return self._http

    async def close(self) -> None:
        if self._http is not None:
            try:
                await self._http.aclose()
            except Exception:
                pass
            self._http = None

    async def get(self, path: str) -> Any:
        try:
            resp = await self._client().get(path)
            resp.raise_for_status()
            self.last_call_ok = True
            return resp.json() if resp.content else None
        except Exception:
            self.last_call_ok = False
            raise

    async def post(self, path: str, payload: Any = None) -> Any:
        try:
            resp = await self._client().post(path, json=payload)
            resp.raise_for_status()
            self.last_call_ok = True
            return resp.json() if resp.content else None
        except Exception:
            self.last_call_ok = False
            raise

    async def put_file(self, path: str, data: bytes) -> Any:
        try:
            resp = await self._client().put(
                path, content=data,
                headers={"Content-Type": "application/octet-stream"})
            resp.raise_for_status()
            self.last_call_ok = True
            return resp.text
        except Exception:
            self.last_call_ok = False
            raise

    # ------------------------------------------------------------------
    # Batched event forwarding
    # ------------------------------------------------------------------

    def enqueue_event(self, event: dict) -> None:
        """Queue an AMI event for delivery. Drops the oldest when full —
        the reconciliation loop emits synthetic hangups for anything the
        webhook never saw."""
        try:
            self._outbox.put_nowait(event)
        except asyncio.QueueFull:
            try:
                self._outbox.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self._outbox.put_nowait(event)
            except asyncio.QueueFull:
                logger.error("Event outbox saturated; event dropped")

    def outbox_depth(self) -> int:
        return self._outbox.qsize()

    async def _collect_batch(self) -> list[dict]:
        batch = [await self._outbox.get()]
        deadline = asyncio.get_running_loop().time() + self.batch_window
        while len(batch) < self.batch_size:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                break
            try:
                batch.append(await asyncio.wait_for(
                    self._outbox.get(), timeout=remaining))
            except asyncio.TimeoutError:
                break
        return batch

    async def outbox_worker(self) -> None:
        """Background task: drain the outbox in batches, retry on errors."""
        while True:
            batch = await self._collect_batch()
            while True:
                try:
                    await self.post("/asterisk/webhook/events", batch)
                    logger.debug("Forwarded %d event(s) to Odoo", len(batch))
                    break
                except Exception as exc:
                    logger.warning(
                        "Event batch POST failed (%s); retrying in %ss",
                        exc, SEND_FAIL_DELAY)
                    await asyncio.sleep(SEND_FAIL_DELAY)
