"""Service entry point.

For now boots the firewall baseline (ipsets + iptables chain) from env
config and the optional JSON cache, then idles. ESL listener, HTTP API
and dashboard are added in subsequent commits.
"""
import asyncio
import logging
import logging.config
import signal

import click

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

logger = logging.getLogger("connect_firewall_service")


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def install_firewall_baseline(settings: ServiceSettings) -> None:
    """Create ipsets and the iptables chain to the desired baseline."""
    # hash:net sets — permanent, no timeout
    ipset_manager.ensure_set(IPSET_WHITELIST, set_type="hash:net")
    ipset_manager.ensure_set(IPSET_BLACKLIST, set_type="hash:net")
    # hash:ip sets — with timeouts
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


async def run(settings: ServiceSettings) -> None:
    logger.info(
        "connect-firewall-service %s starting (Odoo=%s, ESL=%s:%s)",
        __version__, settings.odoo_url,
        settings.fs_esl_host, settings.fs_esl_port,
    )

    if settings.firewall_enabled:
        try:
            install_firewall_baseline(settings)
        except Exception:
            logger.exception("Failed to install firewall baseline")
    else:
        logger.info("firewall_enabled=False — baseline not installed")

    # Idle loop until SIGTERM/SIGINT — replaced by real services in later commits.
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    logger.info("waiting for signal to exit")
    await stop.wait()
    logger.info("shutting down")


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
