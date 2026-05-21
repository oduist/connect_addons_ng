"""Translate ESL events into ipset moves and Odoo reports.

The mapping is the FreeSWITCH equivalent of the Asterisk reference:

  * ``sofia::register_attempt`` / ``sofia::pre_register`` with no
    successful auth-result yet -> the IP gets a 30-second pass through
    ``expire_short`` plus a 24-hour default-deny entry in
    ``expire_long``;
  * ``sofia::register`` (a successful registration) -> the IP enters
    ``authenticated`` for 7 days and we drop the default-deny entry;
  * ``sofia::register_failure`` -> the IP enters ``banned`` for 24
    hours and is removed from ``expire_long``.

Field names vary slightly across mod_sofia versions, so we look up the
remote address and User-Agent from a small list of likely headers; if
none match the event is logged at DEBUG and ignored.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Optional

from . import ipset_manager
from .constants import (
    IPSET_AUTHENTICATED,
    IPSET_BANNED,
    IPSET_EXPIRE_LONG,
    IPSET_EXPIRE_SHORT,
    addr_is_private,
)
from .odoo_client import OdooClient

logger = logging.getLogger(__name__)

# Headers we try, in order, to find the remote SIP IP. The asterisk-side
# agent reads ``RemoteAddress`` (``IPV4/UDP/1.2.3.4/5060``); FreeSWITCH
# usually exposes the bare IP in one of these.
_IP_HEADER_CANDIDATES = (
    "Network-Ip", "Network-IP", "network-ip",
    "From-Host", "from-host",
    "Contact-Host", "contact-host",
    "sip_from_host", "sip_contact_host",
    "Remote-IP", "Remote-Ip",
)

# Some FreeSWITCH builds wrap the address in ``IPV4/UDP/1.2.3.4/5060`` —
# this regex extracts the first IPv4 we can find.
_IPV4_RE = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")


def _extract_ip(event: Mapping[str, str]) -> Optional[str]:
    for key in _IP_HEADER_CANDIDATES:
        val = event.get(key)
        if not val:
            continue
        m = _IPV4_RE.search(val)
        if m:
            return m.group(0)
    return None


def _extract_user_agent(event: Mapping[str, str]) -> str:
    return (
        event.get("User-Agent")
        or event.get("user-agent")
        or event.get("sip_user_agent")
        or ""
    )


def _extract_account(event: Mapping[str, str]) -> str:
    return (
        event.get("username")
        or event.get("from-user")
        or event.get("From-User")
        or event.get("sip_from_user")
        or ""
    )


def _is_success(event: Mapping[str, str]) -> bool:
    """Best-effort detection of a successful register on register_attempt."""
    for key in ("auth-result", "Auth-Result"):
        v = event.get(key)
        if v and v.upper() in ("AUTHENTICATED", "OK"):
            return True
    return False


class ESLHandler:
    def __init__(self, odoo: OdooClient, banned_ttl: int, trust_ttl: int,
                 expire_short_ttl: int, expire_long_ttl: int):
        self.odoo = odoo
        self.banned_ttl = banned_ttl
        self.trust_ttl = trust_ttl
        self.expire_short_ttl = expire_short_ttl
        self.expire_long_ttl = expire_long_ttl

    def handle(self, event: Mapping[str, str]) -> None:
        subclass = (
            event.get("Event-Subclass")
            or event.get("event-subclass")
            or ""
        )
        if not subclass.startswith("sofia::"):
            return

        ip = _extract_ip(event)
        if not ip:
            logger.debug("ESL %s without resolvable IP: %s", subclass, dict(event))
            return
        if addr_is_private(ip):
            logger.debug("Ignoring %s from private %s", subclass, ip)
            return

        ua = _extract_user_agent(event)
        account = _extract_account(event)
        comment = "{} {} {}".format(subclass, account, ua)[:255]

        if subclass == "sofia::register" or _is_success(event):
            ipset_manager.add_entry(
                IPSET_AUTHENTICATED, ip, comment=comment,
                timeout=self.trust_ttl,
            )
            ipset_manager.del_entry(IPSET_EXPIRE_LONG, ip)
            self.odoo.enqueue(
                "report_event",
                {"event_type": "auth_success", "ip": ip,
                 "user_agent": ua, "account_id": account,
                 "details": subclass},
            )
            logger.info("AUTH SUCCESS %s (user=%s)", ip, account)
            return

        if subclass in ("sofia::register_attempt", "sofia::pre_register"):
            ipset_manager.add_entry(
                IPSET_EXPIRE_SHORT, ip, comment=comment,
                timeout=self.expire_short_ttl,
            )
            ipset_manager.add_entry(
                IPSET_EXPIRE_LONG, ip, comment=comment,
                timeout=self.expire_long_ttl,
            )
            logger.debug("CHALLENGE %s (user=%s)", ip, account)
            return

        if subclass == "sofia::register_failure":
            ipset_manager.add_entry(
                IPSET_BANNED, ip, comment=comment, timeout=self.banned_ttl,
            )
            ipset_manager.del_entry(IPSET_EXPIRE_LONG, ip)
            self.odoo.enqueue(
                "report_event",
                {"event_type": "auto_ban", "ip": ip,
                 "user_agent": ua, "account_id": account,
                 "details": subclass},
            )
            logger.info("AUTO-BAN %s (user=%s, ua=%s)", ip, account, ua)
            return

        # Other sofia::* events we don't act on (expire, gateway etc.).
        logger.debug("Unhandled sofia subclass %s for %s", subclass, ip)
