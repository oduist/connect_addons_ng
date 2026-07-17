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
    IPV6_SET_SUFFIX,
)
from . import iptables_manager, ipset_manager
from .esl import ESLClient
from .esl_handler import ESLHandler
from .event_bus import EventBus
from .http_server import build_app
from .odoo_client import OdooClient
from .reconciler import Reconciler

logger = logging.getLogger("connect_firewall_service")

# ESL needs the CUSTOM event-class first, then the specific subclasses
# we care about. Listing them explicitly keeps the bus quiet and avoids
# missing events that some sofia builds do not deliver under a bare
# ``events plain CUSTOM`` subscription.
ESL_SUBSCRIPTIONS = (
    "CUSTOM",
    "sofia::pre_register",
    "sofia::register_attempt",
    "sofia::register",
    "sofia::register_failure",
    "sofia::expire",
    "sofia::wrong_call_state",
)


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Quiet down very noisy libraries even at DEBUG level.
    for name in ("httpcore", "httpcore.http11", "httpcore.connection", "httpx"):
        logging.getLogger(name).setLevel(logging.INFO)


def install_firewall_baseline(settings: ServiceSettings) -> None:
    # Every set exists per address family: base name = IPv4 (inet),
    # "6"-suffixed twin = IPv6 (inet6).
    for family, suffix in (("inet", ""), ("inet6", IPV6_SET_SUFFIX)):
        ipset_manager.ensure_set(
            IPSET_WHITELIST + suffix, family=family, set_type="hash:net",
        )
        ipset_manager.ensure_set(
            IPSET_BLACKLIST + suffix, family=family, set_type="hash:net",
        )
        ipset_manager.ensure_set(
            IPSET_AUTHENTICATED + suffix, family=family,
            timeout=settings.firewall_authenticated_timeout,
        )
        ipset_manager.ensure_set(
            IPSET_BANNED + suffix, family=family,
            timeout=settings.firewall_banned_timeout,
        )
        ipset_manager.ensure_set(
            IPSET_EXPIRE_SHORT + suffix, family=family,
            timeout=settings.firewall_expire_short_timeout,
        )
        ipset_manager.ensure_set(
            IPSET_EXPIRE_LONG + suffix, family=family,
            timeout=settings.firewall_expire_long_timeout,
        )
    iptables_manager.apply_baseline(
        settings.firewall_tcp_ports, settings.firewall_udp_ports,
    )


async def esl_loop(handler: ESLHandler, client: ESLClient) -> None:
    async for event in client.events():
        # Trace at DEBUG so a quick log peek shows exactly which subclass
        # arrived; spec is "Event-Name / Event-Subclass: from-user".
        logger.debug(
            "ESL recv: %s / %s (from=%s, contact=%s, auth-result=%s)",
            event.get("Event-Name"),
            event.get("Event-Subclass"),
            event.get("from-user") or event.get("username"),
            event.get("contact"),
            event.get("auth-result"),
        )
        try:
            handler.handle(event)
        except Exception:
            logger.exception("ESL handler error")


async def heartbeat_loop(settings: ServiceSettings, odoo: OdooClient,
                         esl_client: ESLClient,
                         started_at: float) -> None:
    while True:
        try:
            bans = ipset_manager.list_entries_all_families(IPSET_BANNED)
            auth = ipset_manager.list_entries_all_families(IPSET_AUTHENTICATED)
            await odoo.post("/heartbeat", {
                "version": __version__,
                "esl_connected": esl_client.is_connected,
                "bans_count": len(bans),
                "authenticated_count": len(auth),
                "uptime_seconds": int(time.time() - started_at),
            })
        except Exception as exc:
            logger.debug("Heartbeat failed: %s", exc)
        await asyncio.sleep(max(15, settings.firewall_heartbeat_interval))


async def run(settings: ServiceSettings) -> None:
    logger.info(
        "connect-firewall-service %s starting (Odoo=%s, ESL=%s:%s, enabled=%s)",
        __version__, settings.odoo_url,
        settings.fs_esl_host, settings.fs_esl_port,
        settings.firewall_enabled,
    )

    # We always install the kernel baseline so the ESL handler can move
    # IPs around even before the operator flips firewall_enabled in
    # Odoo. The chain just isn't useful until they do — until then the
    # default-ACCEPT terminator at the bottom keeps traffic flowing.
    try:
        install_firewall_baseline(settings)
    except Exception:
        logger.exception(
            "install_firewall_baseline failed — check that the container "
            "runs with --cap-add=NET_ADMIN and ipset/iptables are available"
        )

    odoo = OdooClient(
        base_url=settings.odoo_url, token=settings.agent_token,
    )

    reconciler = Reconciler(settings=settings, odoo=odoo)
    # First sync is fire-and-forget; the Reconciler loop handles errors.
    reconciler.trigger("all")

    event_bus = EventBus()
    handler = ESLHandler(
        odoo=odoo,
        event_bus=event_bus,
        banned_ttl=settings.firewall_banned_timeout,
        trust_ttl=settings.firewall_authenticated_timeout,
        expire_short_ttl=settings.firewall_expire_short_timeout,
        expire_long_ttl=settings.firewall_expire_long_timeout,
    )
    esl_client = ESLClient(
        host=settings.fs_esl_host,
        port=settings.fs_esl_port,
        password=settings.fs_esl_password,
        subscriptions=ESL_SUBSCRIPTIONS,
    )

    started_at = time.time()
    app = build_app(settings, reconciler, odoo, esl_client, event_bus, started_at)

    # Own the uvicorn server so the shutdown path can drive its graceful
    # stop directly. timeout_graceful_shutdown bounds how long uvicorn waits
    # for in-flight connections: the SSE /firewall/events stream is
    # long-lived and would otherwise hold shutdown open indefinitely (the
    # dashboard reconnects on its own, so a force-close after a few seconds
    # is fine).
    http_config = uvicorn.Config(
        app,
        host=settings.http_bind_host,
        port=settings.http_bind_port,
        log_level=settings.log_level.lower(),
        access_log=False,
        timeout_graceful_shutdown=5,
    )
    http_server = uvicorn.Server(http_config)
    # We install our own SIGTERM/SIGINT handlers below; keep uvicorn from
    # replacing them with its own (its handler would trap the signal and
    # race our stop-event, breaking the coordinated shutdown).
    http_server.install_signal_handlers = lambda: None

    def _log_task_exception(task: asyncio.Task) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error("Task %s crashed: %s", task.get_name(), exc, exc_info=exc)

    tasks = [
        asyncio.create_task(odoo.outbox_worker(), name="outbox"),
        asyncio.create_task(esl_loop(handler, esl_client), name="esl"),
        asyncio.create_task(
            heartbeat_loop(settings, odoo, esl_client, started_at),
            name="heartbeat",
        ),
        asyncio.create_task(reconciler.run(), name="reconciler"),
    ]
    http_task = asyncio.create_task(http_server.serve(), name="http")
    for t in (*tasks, http_task):
        t.add_done_callback(_log_task_exception)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    logger.info("running — waiting for signal")
    await stop.wait()

    logger.info("shutting down")
    # Ask uvicorn to unwind its own lifespan cleanly: should_exit makes
    # serve() return after emitting the ASGI lifespan.shutdown event, so the
    # lifespan task is never cancelled mid-receive() — which is exactly what
    # produced the CancelledError traceback on every stop. The background
    # loops are plain infinite tasks, so cancelling them is quiet.
    http_server.should_exit = True
    with suppress(asyncio.CancelledError, Exception):
        await http_task
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
