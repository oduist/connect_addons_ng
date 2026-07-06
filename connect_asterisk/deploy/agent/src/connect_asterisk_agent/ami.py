"""Tiny async AMI client.

The full Asterisk Manager Interface is rich, but the agent only needs:
login, an async iterator over events, and request/response actions with
``ActionID`` correlation (including ``EventList`` collection for
multi-event responses like ``CoreShowChannels``). Hand-rolled in the
style of the firewall service's ESL client — pulling an unmaintained
AMI library into a customer-side sidecar is worse than ~300 lines of
our own code.

Wire format reminder:
    Key: Value\r\n
    Key: Value\r\n
    \r\n
The server greets with a single banner line ``Asterisk Call
Manager/X.Y\r\n`` before the first message block.
"""
from __future__ import annotations

import asyncio
import itertools
import logging
import time
from typing import AsyncIterator, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

EVENT_QUEUE_MAX = 10000


class AMIAuthError(Exception):
    pass


class AMIActionTimeout(Exception):
    pass


def parse_lines(lines: list[str]) -> dict:
    """Parse one AMI message block into a dict (last value wins)."""
    message: dict[str, str] = {}
    for line in lines:
        key, sep, value = line.partition(":")
        if not sep:
            continue
        message[key.strip()] = value.strip()
    return message


class _Pending:
    __slots__ = ("future", "collect", "events")

    def __init__(self, collect: bool):
        self.future: asyncio.Future = asyncio.get_running_loop().create_future()
        self.collect = collect
        self.events: list[dict] = []


class AMIClient:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        secret: str,
        event_mask: str = "call,dialplan,user",
        ping_interval: float = 30.0,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.secret = secret
        self.event_mask = event_mask
        self.ping_interval = ping_interval
        self.is_connected = False
        self.asterisk_banner = ""
        self.on_connect: Optional[Callable[[], Awaitable[None]]] = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._events: asyncio.Queue[dict] = asyncio.Queue(maxsize=EVENT_QUEUE_MAX)
        self._pending: dict[str, _Pending] = {}
        self._action_seq = itertools.count(1)
        self._send_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Low-level I/O
    # ------------------------------------------------------------------

    async def _read_block(self) -> dict:
        assert self._reader is not None
        lines: list[str] = []
        while True:
            raw = await self._reader.readline()
            if not raw:
                raise ConnectionError("AMI connection closed")
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            if not line:
                if lines:
                    break
                continue  # tolerate stray blank lines
            lines.append(line)
        return parse_lines(lines)

    async def _send_action(self, fields: dict) -> None:
        assert self._writer is not None
        payload = "".join(
            "{}: {}\r\n".format(key, item)
            for key, value in fields.items()
            # AMI represents repeated headers (Variable: a=b) as lists.
            for item in (value if isinstance(value, (list, tuple)) else [value])
        ) + "\r\n"
        async with self._send_lock:
            self._writer.write(payload.encode())
            await self._writer.drain()

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def _open(self) -> None:
        self._reader, self._writer = await asyncio.open_connection(
            self.host, self.port)
        banner = await self._reader.readline()
        self.asterisk_banner = banner.decode("utf-8", "replace").strip()
        await self._send_action({
            "Action": "Login",
            "ActionID": "login",
            "Username": self.username,
            "Secret": self.secret,
            "Events": self.event_mask,
        })
        reply = await self._read_block()
        if reply.get("Response") != "Success":
            raise AMIAuthError(
                "AMI login failed: " + (reply.get("Message") or "?"))
        self.is_connected = True
        logger.info("AMI connected to %s:%s (%s)",
                    self.host, self.port, self.asterisk_banner)

    async def close(self) -> None:
        self.is_connected = False
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None

    def _fail_pending(self, exc: Exception) -> None:
        for pending in self._pending.values():
            if not pending.future.done():
                pending.future.set_exception(exc)
        self._pending.clear()

    # ------------------------------------------------------------------
    # Reader / keepalive loops
    # ------------------------------------------------------------------

    def _dispatch(self, message: dict) -> None:
        action_id = message.get("ActionID", "")
        pending = self._pending.get(action_id)
        if pending is not None:
            if "Response" in message:
                event_list = message.get("EventList", "")
                if pending.collect and event_list.lower() == "start":
                    return  # events follow; keep collecting
                if not pending.future.done():
                    pending.future.set_result(
                        pending.events if pending.collect else message)
                if not pending.collect:
                    self._pending.pop(action_id, None)
                return
            # Event that belongs to a collected response.
            if message.get("EventList", "").lower() == "complete":
                if not pending.future.done():
                    pending.future.set_result(pending.events)
                self._pending.pop(action_id, None)
                return
            if pending.collect:
                pending.events.append(message)
                return
        if "Event" in message:
            try:
                self._events.put_nowait(message)
            except asyncio.QueueFull:
                # Shed the oldest event; the reconciler heals state gaps.
                try:
                    self._events.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    self._events.put_nowait(message)
                except asyncio.QueueFull:
                    logger.error("AMI event queue saturated; event dropped")

    async def _ping_loop(self) -> None:
        """Detect half-open TCP (NAT/conntrack timeouts) proactively."""
        while True:
            await asyncio.sleep(self.ping_interval)
            try:
                await self.action({"Action": "Ping"}, timeout=10)
            except Exception as exc:
                logger.warning("AMI ping failed (%s); resetting connection",
                               exc)
                await self.close()
                return

    async def run(self) -> None:
        """Supervisor: keep the connection alive forever with backoff."""
        backoff = 1.0
        while True:
            ping_task = None
            try:
                await self._open()
                backoff = 1.0
                if self.on_connect is not None:
                    asyncio.ensure_future(self.on_connect())
                ping_task = asyncio.create_task(self._ping_loop())
                while True:
                    message = await self._read_block()
                    self._dispatch(message)
            except Exception as exc:
                self.is_connected = False
                self._fail_pending(ConnectionError("AMI reconnecting"))
                logger.warning(
                    "AMI connection lost (%s); reconnecting in %.1fs",
                    exc, backoff)
                if ping_task is not None:
                    ping_task.cancel()
                await self.close()
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def events(self) -> AsyncIterator[dict]:
        while True:
            yield await self._events.get()

    async def action(self, fields: dict, timeout: float = 5.0,
                     collect_events: bool = False):
        """Send an action and await its response.

        Returns the response message dict, or the list of collected
        events when ``collect_events`` is True (``CoreShowChannels``).
        """
        if not self.is_connected:
            raise ConnectionError("AMI is not connected")
        action_id = "{}-{}".format(int(time.time()), next(self._action_seq))
        fields = dict(fields)
        fields["ActionID"] = action_id
        pending = _Pending(collect=collect_events)
        self._pending[action_id] = pending
        try:
            await self._send_action(fields)
            return await asyncio.wait_for(pending.future, timeout)
        except asyncio.TimeoutError:
            raise AMIActionTimeout(
                "AMI action {} timed out after {}s".format(
                    fields.get("Action"), timeout))
        finally:
            self._pending.pop(action_id, None)
