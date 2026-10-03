# -*- coding: utf-8 -*-
import logging

logger = logging.getLogger(__name__)

DEFAULT_ICE_SERVERS = (
    "stun:stun.l.google.com:19302\n"
    "stun:stun1.l.google.com:19302\n"
    "stun:stun.cloudflare.com:3478\n"
    "stun:stun.nextcloud.com:443"
)


def migrate(cr, version):
    """Populate default ICE servers for existing installations."""
    cr.execute(
        "UPDATE connect_settings SET freeswitch_ice_servers = %s "
        "WHERE freeswitch_ice_servers IS NULL",
        (DEFAULT_ICE_SERVERS,),
    )
    updated = cr.rowcount
    logger.info("Set default ICE servers on %d settings record(s)", updated)
