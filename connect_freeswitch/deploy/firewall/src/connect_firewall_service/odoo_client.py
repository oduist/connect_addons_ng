"""Async XML-RPC client for the paired Odoo + an in-memory outbox.

We keep this thin: just enough to call methods on
``connect.firewall.agent`` under the portal user. The outbox is a plain
asyncio.Queue + background task — if Odoo is down the queue grows in
memory; the kernel-level firewall keeps working regardless.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from aio_odoorpc import AsyncOdooRPC

logger = logging.getLogger(__name__)

OUTBOX_MAX = 5000
RECONNECT_DELAY = 5.0
SEND_FAIL_DELAY = 5.0


class OdooClient:
    def __init__(self, url: str, db: str, user: str, password: str):
        self.url = url.rstrip("/")
        self.db = db
        self.user = user
        self.password = password
        self._http: httpx.AsyncClient | None = None
        self._rpc: AsyncOdooRPC | None = None
        self._outbox: asyncio.Queue[tuple[str, tuple, dict]] = asyncio.Queue(
            maxsize=OUTBOX_MAX,
        )
        self._connected = asyncio.Event()

    # ------------------------------------------------------------------
    # Connect / call
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=self.url + "/jsonrpc", follow_redirects=True,
            )
        self._rpc = AsyncOdooRPC(
            database=self.db,
            username_or_uid=self.user,
            password=self.password,
            http_client=self._http,
        )
        try:
            ok = await self._rpc.login()
        except Exception as exc:
            logger.warning("Odoo login error: %s", exc)
            return False
        if not ok:
            logger.warning("Odoo login returned False")
            return False
        logger.info("Connected to Odoo at %s as %s", self.url, self.user)
        self._connected.set()
        return True

    async def close(self) -> None:
        self._connected.clear()
        if self._http is not None:
            try:
                await self._http.aclose()
            except Exception:
                pass
            self._http = None
        self._rpc = None

    async def call(self, method: str, args: list | None = None, kwargs: dict | None = None) -> Any:
        """Synchronous (awaitable) call to connect.firewall.agent.<method>."""
        if self._rpc is None:
            raise RuntimeError("Odoo client not connected")
        return await self._rpc.execute_kw(
            model_name="connect.firewall.agent",
            method=method,
            args=args or [],
            kwargs=kwargs or {},
        )

    # ------------------------------------------------------------------
    # Async fire-and-forget via the outbox
    # ------------------------------------------------------------------

    def enqueue(self, method: str, *args: Any, **kwargs: Any) -> None:
        """Schedule a call without awaiting Odoo. Drops oldest if full."""
        try:
            self._outbox.put_nowait((method, args, kwargs))
        except asyncio.QueueFull:
            try:
                self._outbox.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self._outbox.put_nowait((method, args, kwargs))
            except asyncio.QueueFull:
                logger.error("Outbox saturated; dropping %s", method)

    async def outbox_worker(self) -> None:
        """Background task: drain the outbox, retrying on errors."""
        while True:
            method, args, kwargs = await self._outbox.get()
            while True:
                if self._rpc is None:
                    if not await self.connect():
                        await asyncio.sleep(RECONNECT_DELAY)
                        continue
                try:
                    await self.call(method, list(args), kwargs)
                    break
                except Exception as exc:
                    logger.warning(
                        "Odoo call %s failed (%s); will retry", method, exc,
                    )
                    await self.close()
                    await asyncio.sleep(SEND_FAIL_DELAY)
