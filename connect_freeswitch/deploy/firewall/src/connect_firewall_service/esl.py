"""Tiny async ESL client.

The full FreeSWITCH ESL protocol is rich, but for firewall purposes we
only need: connect, authenticate, subscribe to a small set of CUSTOM
event subclasses, and read events forever. That's what this module
provides — a single ``ESLClient`` class with auto-reconnect and an
async iterator over decoded events.

Wire format reminder:
    <header>: <value>\r\n
    <header>: <value>\r\n
    \r\n
    [optional body of Content-Length bytes]
"""
from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
from typing import AsyncIterator, Iterable

logger = logging.getLogger(__name__)


class ESLAuthError(Exception):
    pass


class ESLClient:
    def __init__(
        self,
        host: str,
        port: int,
        password: str,
        subscriptions: Iterable[str] = (),
    ):
        self.host = host
        self.port = port
        self.password = password
        self.subscriptions = list(subscriptions)
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    # ------------------------------------------------------------------
    # Low-level I/O
    # ------------------------------------------------------------------

    async def _read_message(self) -> OrderedDict[str, str]:
        """Read one full ESL message (headers + optional body)."""
        assert self._reader is not None
        headers: OrderedDict[str, str] = OrderedDict()
        while True:
            line = await self._reader.readline()
            if not line:
                raise ConnectionError("ESL connection closed")
            line = line.rstrip(b"\r\n")
            if not line:
                break
            try:
                key, _, value = line.decode("utf-8", "replace").partition(":")
                headers[key.strip()] = value.strip()
            except Exception:
                continue
        length = int(headers.get("Content-Length") or 0)
        if length:
            body = await self._reader.readexactly(length)
            content_type = headers.get("Content-Type", "")
            if content_type == "text/event-plain":
                # The body itself is a header block — merge it into the
                # outer dict so callers see one flat mapping.
                for raw in body.decode("utf-8", "replace").split("\n"):
                    raw = raw.rstrip("\r")
                    if not raw or ":" not in raw:
                        continue
                    k, _, v = raw.partition(":")
                    headers[k.strip()] = v.strip()
            else:
                headers["_body"] = body.decode("utf-8", "replace")
        return headers

    async def _send(self, line: str) -> None:
        assert self._writer is not None
        self._writer.write((line + "\n\n").encode())
        await self._writer.drain()

    # ------------------------------------------------------------------
    # Connect / authenticate / subscribe
    # ------------------------------------------------------------------

    async def _open(self) -> None:
        self._reader, self._writer = await asyncio.open_connection(
            self.host, self.port,
        )
        banner = await self._read_message()
        if banner.get("Content-Type") != "auth/request":
            raise ESLAuthError(
                "Unexpected ESL banner: " + (banner.get("Content-Type") or "?")
            )
        await self._send("auth " + self.password)
        reply = await self._read_message()
        if not reply.get("Reply-Text", "").startswith("+OK"):
            raise ESLAuthError(
                "ESL auth failed: " + (reply.get("Reply-Text") or "?")
            )
        if self.subscriptions:
            await self._send("events plain " + " ".join(self.subscriptions))
            reply = await self._read_message()
            if not reply.get("Reply-Text", "").startswith("+OK"):
                raise ESLAuthError(
                    "ESL subscribe failed: " + (reply.get("Reply-Text") or "?")
                )
        logger.info(
            "ESL connected to %s:%s, subscriptions=%s",
            self.host, self.port, self.subscriptions or "ALL",
        )

    async def close(self) -> None:
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None

    # ------------------------------------------------------------------
    # Public: iterate events forever with auto-reconnect
    # ------------------------------------------------------------------

    async def events(self) -> AsyncIterator[OrderedDict[str, str]]:
        """Yield events forever; reconnects with backoff on disconnect."""
        backoff = 1.0
        while True:
            try:
                await self._open()
                backoff = 1.0
                while True:
                    msg = await self._read_message()
                    yield msg
            except Exception as exc:
                logger.warning(
                    "ESL connection lost (%s); reconnecting in %.1fs",
                    exc, backoff,
                )
                await self.close()
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
