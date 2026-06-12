"""Agent entry point.

Bootstraps:
  * the AMI client (persistent connection, reconnect, keepalive);
  * the event pipeline (filter → trim → batched POST to Odoo webhooks);
  * the recording uploader;
  * the reconciler (config pull + CoreShowChannels healing);
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
from .ami import AMIClient
from .ami_handler import AMIHandler
from .call_state import CallState
from .config import (
    AgentSettings,
    apply_cache_to_settings,
    load_runtime_cache,
)
from .constants import AMI_EVENT_MASK, DEFAULT_EVENTS
from .http_server import build_app
from .odoo_client import OdooClient
from .recordings import RecordingUploader
from .reconciler import Reconciler

logger = logging.getLogger("connect_asterisk_agent")


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    for name in ("httpcore", "httpcore.http11", "httpcore.connection",
                 "httpx"):
        logging.getLogger(name).setLevel(logging.INFO)


async def ami_loop(handler: AMIHandler, ami: AMIClient) -> None:
    async for event in ami.events():
        try:
            handler.handle(event)
        except Exception:
            logger.exception("AMI handler error")


async def heartbeat_loop(settings: AgentSettings, odoo: OdooClient,
                         ami: AMIClient, started_at: float) -> None:
    while True:
        try:
            await odoo.post("/asterisk/webhook/heartbeat", {
                "version": __version__,
                "ami_connected": ami.is_connected,
                "asterisk_banner": ami.asterisk_banner,
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
        "connect-asterisk-agent %s starting (Odoo=%s, AMI=%s:%s)",
        __version__, settings.odoo_url,
        settings.ami_host, settings.ami_port,
    )

    odoo = OdooClient(
        base_url=settings.odoo_url,
        token=settings.agent_token,
        batch_size=settings.event_batch_size,
        batch_window=settings.event_batch_window,
    )
    call_state = CallState(ttl=settings.call_state_ttl)
    recordings = None
    if settings.recordings_enabled:
        recordings = RecordingUploader(
            odoo=odoo,
            state_path=settings.state_path,
            upload_delay=settings.recording_upload_delay,
            max_mb=settings.recording_max_mb,
            retry_hours=settings.recording_retry_hours,
            delete_after_upload=settings.recording_delete_after_upload,
        )
    events = tuple(
        e.strip() for e in settings.events.split(",") if e.strip()
    ) or DEFAULT_EVENTS
    handler = AMIHandler(
        odoo=odoo,
        call_state=call_state,
        recordings=recordings,
        events=events,
        trace=settings.ami_trace,
    )
    ami = AMIClient(
        host=settings.ami_host,
        port=settings.ami_port,
        username=settings.ami_user,
        secret=settings.ami_password,
        event_mask=AMI_EVENT_MASK,
        ping_interval=settings.ami_ping_interval,
    )
    reconciler = Reconciler(
        settings=settings, odoo=odoo, ami=ami,
        handler=handler, call_state=call_state,
    )

    async def _on_ami_connect() -> None:
        # Heal whatever happened while AMI was down.
        reconciler.trigger("channels")

    ami.on_connect = _on_ami_connect

    started_at = time.time()
    app = build_app(settings, ami, odoo, handler, call_state,
                    recordings, reconciler, started_at)

    def _log_task_exception(task: asyncio.Task) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error("Task %s crashed: %s",
                         task.get_name(), exc, exc_info=exc)

    tasks = [
        asyncio.create_task(ami.run(), name="ami"),
        asyncio.create_task(ami_loop(handler, ami), name="ami-events"),
        asyncio.create_task(odoo.outbox_worker(), name="outbox"),
        asyncio.create_task(
            heartbeat_loop(settings, odoo, ami, started_at),
            name="heartbeat"),
        asyncio.create_task(reconciler.run(), name="reconciler"),
        asyncio.create_task(http_loop(settings, app), name="http"),
    ]
    if recordings is not None:
        tasks.append(asyncio.create_task(
            recordings.worker(), name="recordings"))
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
    await ami.close()


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
