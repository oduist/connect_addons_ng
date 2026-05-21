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
from .event_bus import EventBus
from .odoo_client import OdooClient

logger = logging.getLogger(__name__)

# Headers we try, in order, to find the remote SIP IP. Bare IP fields
# come first (some sofia events expose ``Network-Ip``); after that we
# fall back to parsing the Contact header where the public IP lives in
# either ``received=<ip>`` (NAT case) or the URI host.
_IP_HEADER_CANDIDATES = (
    # Channel-variable form (lower-case, underscores) — used by
    # sofia::wrong_call_state and several other CUSTOM events.
    "network_ip", "remote_ip", "sip_from_host", "sip_contact_host",
    # Header-style form some sofia builds expose for register events.
    "Network-Ip", "Network-IP", "network-ip",
    "Remote-IP", "Remote-Ip", "remote-ip",
    "From-Host", "from-host",
)

_IPV4_RE = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
_RECEIVED_RE = re.compile(r"received=(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")
_SIP_HOST_RE = re.compile(r"sip:[^@>]+@(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")


def _extract_ip(event: Mapping[str, str]) -> Optional[str]:
    for key in _IP_HEADER_CANDIDATES:
        val = event.get(key)
        if not val:
            continue
        m = _IPV4_RE.search(val)
        if m:
            return m.group(0)
    # Fall back to the Contact header. NAT'ed clients put the public IP
    # in ``received=``; non-NAT clients put it straight in the URI.
    for key in ("contact", "Contact"):
        val = event.get(key)
        if not val:
            continue
        m = _RECEIVED_RE.search(val)
        if m:
            return m.group(1)
        m = _SIP_HOST_RE.search(val)
        if m:
            return m.group(1)
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
        or event.get("from_user")
        or event.get("From-User")
        or event.get("sip_from_user")
        or ""
    )


def _auth_result(event: Mapping[str, str]) -> Optional[str]:
    for key in ("auth-result", "Auth-Result"):
        v = event.get(key)
        if v:
            return v.upper()
    return None


def _is_success(event: Mapping[str, str]) -> bool:
    """Best-effort detection of a successful register on register_attempt."""
    r = _auth_result(event)
    return r in ("AUTHENTICATED", "OK")


def _is_auth_failure(event: Mapping[str, str]) -> bool:
    r = _auth_result(event)
    return r in ("FORBIDDEN", "DENIED", "INVALID")


class ESLHandler:
    def __init__(self, odoo: OdooClient, event_bus: EventBus,
                 banned_ttl: int, trust_ttl: int,
                 expire_short_ttl: int, expire_long_ttl: int):
        self.odoo = odoo
        self.event_bus = event_bus
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
            ipset_manager.del_entry(IPSET_BANNED, ip)
            self.odoo.enqueue(
                "report_event",
                {"event_type": "auth_success", "ip": ip,
                 "user_agent": ua, "account_id": account,
                 "details": subclass},
            )
            self.event_bus.record({
                "type": "auth_success", "ip": ip,
                "user_agent": ua, "account_id": account,
            })
            logger.info("AUTH SUCCESS %s (user=%s)", ip, account)
            return

        # register_attempt with auth-result FORBIDDEN/DENIED/INVALID is
        # the failure path on modern sofia — it does not always emit a
        # separate register_failure right after, so ban here.
        if subclass == "sofia::register_attempt" and _is_auth_failure(event):
            ipset_manager.add_entry(
                IPSET_BANNED, ip, comment=comment, timeout=self.banned_ttl,
            )
            ipset_manager.del_entry(IPSET_EXPIRE_LONG, ip)
            self.odoo.enqueue(
                "report_event",
                {"event_type": "auto_ban", "ip": ip,
                 "user_agent": ua, "account_id": account,
                 "details": "{} ({})".format(subclass, _auth_result(event) or "?")},
            )
            self.event_bus.record({
                "type": "auto_ban", "ip": ip,
                "user_agent": ua, "account_id": account,
                "ttl": self.banned_ttl,
            })
            logger.info("AUTO-BAN %s (user=%s, ua=%s, attempt FORBIDDEN)", ip, account, ua)
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
            self.event_bus.record({
                "type": "challenge", "ip": ip,
                "user_agent": ua, "account_id": account,
            })
            logger.debug("CHALLENGE %s (user=%s)", ip, account)
            return

        if subclass in ("sofia::register_failure", "sofia::wrong_call_state"):
            # wrong_call_state fires on INVITE without an established
            # session — that's toll-fraud territory, ban immediately.
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
            self.event_bus.record({
                "type": "auto_ban", "ip": ip,
                "user_agent": ua, "account_id": account,
                "ttl": self.banned_ttl,
            })
            logger.info("AUTO-BAN %s (user=%s, ua=%s, %s)", ip, account, ua, subclass)
            return

        # Other sofia::* events we don't act on (expire, gateway etc.).
        logger.debug("Unhandled sofia subclass %s for %s", subclass, ip)
