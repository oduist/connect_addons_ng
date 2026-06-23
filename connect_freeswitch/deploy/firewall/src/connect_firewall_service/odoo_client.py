"""HTTP client for the paired Odoo + an in-memory outbox.

Talks to /freeswitch/firewall/api/* on Odoo, authenticated with the
shared ``firewall_service_token`` carried as ``Authorization: Bearer
<token>``. The outbox is a plain asyncio.Queue + background task —
when Odoo is down the queue grows in memory; the kernel-level
firewall keeps working regardless.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Iterable

import httpx

logger = logging.getLogger(__name__)

OUTBOX_MAX = 5000
SEND_FAIL_DELAY = 5.0
REQUEST_TIMEOUT = 10.0


class OdooClient:
    def __init__(self, base_url: str, token: str):
        self.base = base_url.rstrip("/") + "/freeswitch/firewall/api"
        self.token = token
        self._http: httpx.AsyncClient | None = None
        self._outbox: asyncio.Queue[tuple[str, dict]] = asyncio.Queue(
            maxsize=OUTBOX_MAX,
        )
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

    async def _request(self, method: str, path: str,
                       payload: dict | None = None) -> Any:
        client = self._client()
        if method == "GET":
            resp = await client.get(path)
        else:
            resp = await client.post(path, json=payload or {})
        resp.raise_for_status()
        self.last_call_ok = True
        if not resp.content:
            return None
        return resp.json()

    async def get(self, path: str) -> Any:
        try:
            return await self._request("GET", path)
        except Exception:
            self.last_call_ok = False
            raise

    async def post(self, path: str, payload: dict | None = None) -> Any:
        try:
            return await self._request("POST", path, payload)
        except Exception:
            self.last_call_ok = False
            raise

    # ------------------------------------------------------------------
    # Async fire-and-forget via the outbox (used for events only;
    # heartbeats are sent synchronously so a stuck Odoo surfaces
    # immediately rather than piling up).
    # ------------------------------------------------------------------

    def enqueue_event(self, payload: dict) -> None:
        """Schedule POST /event without awaiting Odoo. Drops oldest if full."""
        self._enqueue("/event", payload)

    def _enqueue(self, path: str, payload: dict) -> None:
        try:
            self._outbox.put_nowait((path, payload))
        except asyncio.QueueFull:
            try:
                self._outbox.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self._outbox.put_nowait((path, payload))
            except asyncio.QueueFull:
                logger.error("Outbox saturated; dropping %s", path)

    async def outbox_worker(self) -> None:
        """Background task: drain the outbox, retrying on errors."""
        while True:
            path, payload = await self._outbox.get()
            while True:
                try:
                    await self.post(path, payload)
                    break
                except Exception as exc:
                    logger.warning(
                        "Odoo POST %s failed (%s); will retry", path, exc,
                    )
                    await asyncio.sleep(SEND_FAIL_DELAY)
