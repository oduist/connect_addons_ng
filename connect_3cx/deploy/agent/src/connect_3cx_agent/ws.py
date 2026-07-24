"""Call Control WebSocket loop.

Connects to ``wss://<pbx>/callcontrol/ws`` with the Bearer token from
the shared token manager, feeds decoded messages to the handler, and
reconnects with exponential backoff. Every (re)connect invalidates the
token first — the WS handshake is the first consumer to notice a token
the PBX has silently dropped (e.g. after a 3CX service restart) — and
triggers a participant reconcile to heal missed events.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Callable

import websockets

from .handler import CallControlHandler
from .tcx_api import ThreeCXClient

logger = logging.getLogger(__name__)

BACKOFF_MIN = 1.0
BACKOFF_MAX = 30.0


class CallControlWS:
    def __init__(self, tcx: ThreeCXClient, handler: CallControlHandler,
                 trace: bool = False):
        self.tcx = tcx
        self.handler = handler
        self.trace = trace
        self.is_connected: bool = False
        self.on_connect: Callable[[], None] | None = None

    async def run(self) -> None:
        backoff = BACKOFF_MIN
        while True:
            if not self.tcx.configured():
                await asyncio.sleep(5)
                continue
            try:
                token = await self.tcx.token()
                url = self.tcx.ws_url
                async with websockets.connect(
                    url,
                    additional_headers={
                        "Authorization": "Bearer " + token},
                ) as ws:
                    logger.info("Call Control WS connected: %s", url)
                    self.is_connected = True
                    backoff = BACKOFF_MIN
                    if self.on_connect is not None:
                        try:
                            self.on_connect()
                        except Exception:
                            logger.exception("on_connect callback failed")
                    async for raw in ws:
                        await self._dispatch(raw)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Call Control WS error: %s", exc)
                # A stale token is the most common handshake failure —
                # force a refresh before the next attempt.
                self.tcx.invalidate_token()
            finally:
                self.is_connected = False
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, BACKOFF_MAX)

    async def _dispatch(self, raw) -> None:
        if self.trace:
            logger.info("WS <<< %s", raw)
        try:
            message = json.loads(raw)
        except (TypeError, ValueError):
            logger.debug("Non-JSON WS frame ignored")
            return
        try:
            await self.handler.handle_message(message)
        except Exception:
            logger.exception("WS message handling error")
