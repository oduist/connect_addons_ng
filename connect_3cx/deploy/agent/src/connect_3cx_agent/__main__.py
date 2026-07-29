"""Agent entry point.

Bootstraps:
  * the 3CX token manager + Call Control WebSocket (reconnect, backoff);
  * the event pipeline (normalize → batched POST to Odoo webhooks);
  * the XAPI recording poller;
  * the reconciler (config pull + participant healing);
  * the HTTP server for Odoo-initiated actions;
  * a heartbeat loop reporting agent status to Odoo.
"""
from __future__ import annotations

import asyncio
import logging
import signal
import time
from contextlib import suppress

import click
import uvicorn

from . import __version__
from .config import (
    AgentSettings,
    apply_cache_to_settings,
    load_runtime_cache,
)
from .handler import CallControlHandler
from .http_server import build_app
from .odoo_client import OdooClient
from .reconciler import Reconciler
from .recordings import RecordingPoller
from .state import ParticipantRegistry
from .tcx_api import ThreeCXClient
from .ws import CallControlWS

logger = logging.getLogger("connect_3cx_agent")


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    for name in ("httpcore", "httpcore.http11", "httpcore.connection",
                 "httpx", "websockets"):
        logging.getLogger(name).setLevel(logging.INFO)


async def heartbeat_loop(settings: AgentSettings, odoo: OdooClient,
                         ws: CallControlWS, tcx: ThreeCXClient,
                         started_at: float) -> None:
    while True:
        try:
            await odoo.post("/3cx/webhook/heartbeat", {
                "version": __version__,
                "ws_connected": ws.is_connected,
                "token_ok": tcx.last_token_ok,
                "uptime_seconds": int(time.time() - started_at),
                "queue_depth": odoo.outbox_depth(),
            })
        except Exception as exc:
            logger.debug("Heartbeat failed: %s", exc)
        await asyncio.sleep(max(15, settings.heartbeat_interval))


async def http_loop(settings: AgentSettings, app) -> None:
    config = uvicorn.Config(
        app,
        host=settings.http_bind_host,
        port=settings.http_bind_port,
        log_level=settings.log_level.lower(),
        access_log=False,
    )
    server = uvicorn.Server(config)
    await server.serve()


async def run(settings: AgentSettings) -> None:
    logger.info(
        "connect-3cx-agent %s starting (Odoo=%s, PBX=%s)",
        __version__, settings.odoo_url, settings.pbx_url or "<from config>",
    )

    odoo = OdooClient(
        base_url=settings.odoo_url,
        token=settings.agent_token,
        batch_size=settings.event_batch_size,
        batch_window=settings.event_batch_window,
    )
    tcx = ThreeCXClient(settings)
    registry = ParticipantRegistry(ttl=settings.participant_ttl)
    handler = CallControlHandler(tcx=tcx, odoo=odoo, registry=registry)
    ws = CallControlWS(tcx=tcx, handler=handler, trace=settings.ws_trace)
    recordings = RecordingPoller(
        tcx=tcx, odoo=odoo, settings=settings,
        state_path=settings.state_path,
    )
    reconciler = Reconciler(
        settings=settings, odoo=odoo, tcx=tcx,
        handler=handler, registry=registry,
    )

    def _on_ws_connect() -> None:
        # Heal whatever happened while the WS was down.
        reconciler.trigger("participants")

    ws.on_connect = _on_ws_connect

    started_at = time.time()
    app = build_app(settings, tcx, odoo, handler, ws,
                    recordings, reconciler, started_at)

    def _log_task_exception(task: asyncio.Task) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error("Task %s crashed: %s",
                         task.get_name(), exc, exc_info=exc)

    tasks = [
        asyncio.create_task(ws.run(), name="callcontrol-ws"),
        asyncio.create_task(odoo.outbox_worker(), name="outbox"),
        asyncio.create_task(
            heartbeat_loop(settings, odoo, ws, tcx, started_at),
            name="heartbeat"),
        asyncio.create_task(reconciler.run(), name="reconciler"),
        asyncio.create_task(http_loop(settings, app), name="http"),
        asyncio.create_task(recordings.worker(), name="recordings"),
    ]
    for task in tasks:
        task.add_done_callback(_log_task_exception)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    logger.info("running — waiting for signal")
    await stop.wait()

    logger.info("shutting down")
    for task in tasks:
        task.cancel()
    for task in tasks:
        with suppress(asyncio.CancelledError, Exception):
            await task
    await odoo.close()
    await tcx.close()


@click.command()
def main() -> None:
    settings = AgentSettings()
    setup_logging(settings.log_level)

    cache = load_runtime_cache(
        settings.state_path.replace("state.json", "config.json"))
    if cache:
        apply_cache_to_settings(settings, cache)
        logger.info("Loaded runtime config cache")

    asyncio.run(run(settings))


if __name__ == "__main__":
    main()
