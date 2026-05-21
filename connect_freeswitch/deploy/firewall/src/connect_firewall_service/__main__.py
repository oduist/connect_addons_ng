"""Service entry point.

Bootstraps:
  * the kernel-level firewall baseline (ipsets + iptables chain);
  * the ESL listener that translates SIP REGISTER events into ipset moves;
  * the Odoo XML-RPC client + outbox worker for event reporting;
  * the Reconciler (initial + on-demand + periodic state pulls from Odoo);
  * the HTTP server (Bearer for Odoo, basic-auth for the dashboard);
  * a heartbeat loop that pings Odoo on a configurable interval.
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
    ServiceSettings,
    apply_cache_to_settings,
    load_runtime_cache,
)
from .constants import (
    IPSET_AUTHENTICATED,
    IPSET_BANNED,
    IPSET_BLACKLIST,
    IPSET_EXPIRE_LONG,
    IPSET_EXPIRE_SHORT,
    IPSET_WHITELIST,
)
from . import iptables_manager, ipset_manager
from .esl import ESLClient
from .esl_handler import ESLHandler
from .http_server import build_app
from .odoo_client import OdooClient
from .reconciler import Reconciler

logger = logging.getLogger("connect_firewall_service")

# Subscribing to CUSTOM gets us the sofia::* events we care about; the
# subclass filter in ESLHandler still narrows the actual processing.
ESL_SUBSCRIPTIONS = ("CUSTOM",)


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def install_firewall_baseline(settings: ServiceSettings) -> None:
    ipset_manager.ensure_set(IPSET_WHITELIST, set_type="hash:net")
    ipset_manager.ensure_set(IPSET_BLACKLIST, set_type="hash:net")
    ipset_manager.ensure_set(
        IPSET_AUTHENTICATED, timeout=settings.firewall_authenticated_timeout,
    )
    ipset_manager.ensure_set(
        IPSET_BANNED, timeout=settings.firewall_banned_timeout,
    )
    ipset_manager.ensure_set(
        IPSET_EXPIRE_SHORT, timeout=settings.firewall_expire_short_timeout,
    )
    ipset_manager.ensure_set(
        IPSET_EXPIRE_LONG, timeout=settings.firewall_expire_long_timeout,
    )
    iptables_manager.apply_baseline(
        settings.firewall_tcp_ports, settings.firewall_udp_ports,
    )


async def esl_loop(settings: ServiceSettings, handler: ESLHandler) -> None:
    client = ESLClient(
        host=settings.fs_esl_host,
        port=settings.fs_esl_port,
        password=settings.fs_esl_password,
        subscriptions=ESL_SUBSCRIPTIONS,
    )
    async for event in client.events():
        try:
            handler.handle(event)
        except Exception:
            logger.exception("ESL handler error")


async def heartbeat_loop(settings: ServiceSettings, odoo: OdooClient,
                         started_at: float) -> None:
    while True:
        try:
            bans = ipset_manager.list_entries(IPSET_BANNED)
            auth = ipset_manager.list_entries(IPSET_AUTHENTICATED)
            await odoo.call("report_heartbeat", [{
                "version": __version__,
                "esl_connected": True,
                "bans_count": len(bans),
                "authenticated_count": len(auth),
                "uptime_seconds": int(time.time() - started_at),
            }])
        except Exception as exc:
            logger.debug("Heartbeat failed: %s", exc)
        await asyncio.sleep(max(15, settings.firewall_heartbeat_interval))


async def http_loop(settings: ServiceSettings, app) -> None:
    config = uvicorn.Config(
        app,
        host=settings.http_bind_host,
        port=settings.http_bind_port,
        log_level=settings.log_level.lower(),
        access_log=False,
    )
    server = uvicorn.Server(config)
    await server.serve()


async def run(settings: ServiceSettings) -> None:
    logger.info(
        "connect-firewall-service %s starting (Odoo=%s, ESL=%s:%s, enabled=%s)",
        __version__, settings.odoo_url,
        settings.fs_esl_host, settings.fs_esl_port,
        settings.firewall_enabled,
    )

    install_firewall_baseline(settings)

    odoo = OdooClient(
        url=settings.odoo_url, db=settings.odoo_db,
        user=settings.odoo_user, password=settings.odoo_password,
    )
    # Try to connect once at boot — the outbox/heartbeat tasks will
    # reconnect transparently if this fails.
    await odoo.connect()

    reconciler = Reconciler(settings=settings, odoo=odoo)
    # First sync is fire-and-forget; the Reconciler loop handles errors.
    reconciler.trigger("all")

    handler = ESLHandler(
        odoo=odoo,
        banned_ttl=settings.firewall_banned_timeout,
        trust_ttl=settings.firewall_authenticated_timeout,
        expire_short_ttl=settings.firewall_expire_short_timeout,
        expire_long_ttl=settings.firewall_expire_long_timeout,
    )

    started_at = time.time()
    app = build_app(settings, reconciler, odoo, started_at)

    tasks = [
        asyncio.create_task(odoo.outbox_worker(), name="outbox"),
        asyncio.create_task(esl_loop(settings, handler), name="esl"),
        asyncio.create_task(heartbeat_loop(settings, odoo, started_at), name="heartbeat"),
        asyncio.create_task(reconciler.run(), name="reconciler"),
        asyncio.create_task(http_loop(settings, app), name="http"),
    ]

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


@click.command()
def main() -> None:
    settings = ServiceSettings()
    setup_logging(settings.log_level)

    cache = load_runtime_cache(settings.config_cache_path)
    if cache:
        apply_cache_to_settings(settings, cache)
        logger.info("Loaded runtime cache from %s", settings.config_cache_path)

    asyncio.run(run(settings))


if __name__ == "__main__":
    main()
