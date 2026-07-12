# -*- coding: utf-8 -*-
import ipaddress
import logging
from datetime import timedelta
from urllib.parse import quote

import requests

from odoo import _, api, fields, models, release
from odoo.exceptions import UserError, ValidationError

logger = logging.getLogger(__name__)

SYNC_HTTP_TIMEOUT = 3  # seconds; reconcile cron is the safety net for misses

# res.groups M2M to res.users was renamed from `users` to `user_ids` in Odoo 19.
_GROUP_USERS_FIELD = 'user_ids' if release.version_info[0] >= 19 else 'users'


def _normalize_ip_or_cidr(value):
    """Validate and canonicalize an IP or CIDR of either family.

    Returns the same spelling ipset prints back (compressed lowercase
    IPv6, host entries without the /32 or /128 suffix, the network
    address for CIDRs, IPv4-mapped IPv6 unwrapped to plain IPv4) so the
    firewall service's string-diff sync and the duplicate constraint
    both compare canonical values. Mirrors net_utils.normalize_entry in
    the service (deliberate copy — Odoo does not import service code).
    """
    if not value:
        raise ValidationError("IP address or CIDR is required.")
    text = str(value).strip()
    try:
        addr = ipaddress.ip_address(text)
    except ValueError:
        pass
    else:
        mapped = getattr(addr, "ipv4_mapped", None)
        return str(mapped or addr)
    try:
        net = ipaddress.ip_network(text, strict=False)
    except ValueError as exc:
        raise ValidationError(
            "Invalid IP or CIDR '{}': {}".format(value, exc)
        )
    if (
        net.version == 6
        and net.prefixlen >= 96
        and net.network_address.ipv4_mapped is not None
        and net.broadcast_address.ipv4_mapped is not None
    ):
        net = ipaddress.ip_network(
            "{}/{}".format(net.network_address.ipv4_mapped, net.prefixlen - 96),
            strict=False,
        )
    if net.prefixlen == net.max_prefixlen:
        return str(net.network_address)
    return str(net)


def _safe_normalize(value):
    """Best-effort normalization for stored rows; None on invalid data."""
    try:
        return _normalize_ip_or_cidr(value)
    except ValidationError:
        return None


class FirewallWhitelist(models.Model):
    _name = "connect.firewall.whitelist"
    _description = "Firewall Whitelist Entry"
    _order = "ip_or_cidr"

    name = fields.Char(required=True, help="Short description, e.g. 'Office NY'")
    ip_or_cidr = fields.Char(
        string="IP or CIDR",
        required=True,
        help="Single IP (1.2.3.4 or 2001:db8::1) or CIDR network "
             "(1.2.3.0/24 or 2001:db8::/64).",
    )
    active = fields.Boolean(default=True)
    note = fields.Text()

    @api.constrains("ip_or_cidr")
    def _check_ip_or_cidr(self):
        for rec in self:
            normalized = _normalize_ip_or_cidr(rec.ip_or_cidr)
            # Compare on normalized values so textual variants of the
            # same entry (incl. legacy pre-normalization rows) collide.
            duplicates = [
                other for other in self.search([("id", "!=", rec.id)])
                if _safe_normalize(other.ip_or_cidr) == normalized
            ]
            if duplicates:
                raise ValidationError(
                    "{} is already in the whitelist.".format(rec.ip_or_cidr)
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("ip_or_cidr"):
                vals["ip_or_cidr"] = _normalize_ip_or_cidr(vals["ip_or_cidr"])
        recs = super().create(vals_list)
        self.env["connect.firewall.agent"]._trigger_sync("whitelist")
        return recs

    def write(self, vals):
        if vals.get("ip_or_cidr"):
            vals = dict(vals, ip_or_cidr=_normalize_ip_or_cidr(vals["ip_or_cidr"]))
        res = super().write(vals)
        self.env["connect.firewall.agent"]._trigger_sync("whitelist")
        return res

    def unlink(self):
        res = super().unlink()
        self.env["connect.firewall.agent"]._trigger_sync("whitelist")
        return res


class FirewallBlacklist(models.Model):
    _name = "connect.firewall.blacklist"
    _description = "Firewall Blacklist Entry (permanent manual ban)"
    _order = "ip_or_cidr"

    name = fields.Char(required=True, help="Short description, e.g. 'VPS attacker'")
    ip_or_cidr = fields.Char(
        string="IP or CIDR",
        required=True,
        help="Single IP (1.2.3.4 or 2001:db8::1) or CIDR network "
             "(1.2.3.0/24 or 2001:db8::/64).",
    )
    active = fields.Boolean(default=True)
    note = fields.Text()

    @api.constrains("ip_or_cidr")
    def _check_ip_or_cidr(self):
        for rec in self:
            normalized = _normalize_ip_or_cidr(rec.ip_or_cidr)
            # Compare on normalized values so textual variants of the
            # same entry (incl. legacy pre-normalization rows) collide.
            duplicates = [
                other for other in self.search([("id", "!=", rec.id)])
                if _safe_normalize(other.ip_or_cidr) == normalized
            ]
            if duplicates:
                raise ValidationError(
                    "{} is already in the blacklist.".format(rec.ip_or_cidr)
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("ip_or_cidr"):
                vals["ip_or_cidr"] = _normalize_ip_or_cidr(vals["ip_or_cidr"])
        recs = super().create(vals_list)
        self.env["connect.firewall.agent"]._trigger_sync("blacklist")
        return recs

    def write(self, vals):
        if vals.get("ip_or_cidr"):
            vals = dict(vals, ip_or_cidr=_normalize_ip_or_cidr(vals["ip_or_cidr"]))
        res = super().write(vals)
        self.env["connect.firewall.agent"]._trigger_sync("blacklist")
        return res

    def unlink(self):
        res = super().unlink()
        self.env["connect.firewall.agent"]._trigger_sync("blacklist")
        return res


class FirewallEvent(models.Model):
    _name = "connect.firewall.event"
    _description = "Firewall Security Event"
    _order = "ts desc, id desc"
    _rec_name = "ip"

    EVENT_TYPES = [
        ("auth_success", "Authentication Success"),
        ("auth_fail", "Authentication Failure"),
        ("auto_ban", "Automatic Ban"),
        ("manual_ban_applied", "Manual Ban Applied"),
        ("manual_unban_applied", "Manual Unban Applied"),
        ("whitelist_changed", "Whitelist Changed"),
        ("blacklist_changed", "Blacklist Changed"),
        ("settings_changed", "Settings Changed"),
        ("service_started", "Service Started"),
        ("service_error", "Service Error"),
    ]

    event_type = fields.Selection(EVENT_TYPES, required=True, index=True)
    ip = fields.Char(string="IP", index=True)
    user_agent = fields.Char(string="User Agent")
    account_id = fields.Char(
        string="Account/Extension",
        help="SIP username from the failed REGISTER/INVITE, if known.",
    )
    service = fields.Char(help="udp/tcp/ws if known.")
    details = fields.Text()
    ts = fields.Datetime(
        string="TS",
        required=True,
        default=fields.Datetime.now,
        index=True,
        help="Timestamp from the service (not Odoo create_date).",
    )
    is_banned = fields.Boolean(
        string="Banned",
        compute="_compute_is_banned",
        help="True if this event's IP is currently in the auto-ban set on "
             "the service. Used to enable the Unban button.",
    )

    def _compute_is_banned(self):
        """Best-effort check whether the IP is still in the live banned set.

        We don't track expiry here — we ask the live ipset via the service's
        public API. If the service is unreachable we fall back to showing
        the button for any auto_ban event so the operator can still try.
        """
        # Cheap path: only resolve service URL once per recordset.
        agent = self.env["connect.firewall.agent"].sudo()
        banned_ips = agent._fetch_live_banned_ips()
        for rec in self:
            if rec.event_type == "auto_ban" and rec.ip:
                rec.is_banned = (
                    rec.ip in banned_ips if banned_ips is not None else True
                )
            else:
                rec.is_banned = False

    def action_unban_ip(self):
        """Tell the firewall service to remove this IP from the banned set."""
        self.ensure_one()
        if not self.ip:
            raise UserError(_("Event has no IP to unban."))
        agent = self.env["connect.firewall.agent"].sudo()
        ok, message = agent._call_service_unban(self.ip)
        if ok:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "type": "success",
                    "title": _("Firewall"),
                    "message": _("Unbanned %s") % self.ip,
                    "sticky": False,
                },
            }
        raise UserError(_("Unban failed: %s") % message)

    @api.model
    def _cron_cleanup(self):
        """Delete events older than firewall_event_retention_days. Called from ir.cron."""
        days = int(
            self.env["connect.settings"].sudo().get_param(
                "firewall_event_retention_days", 30
            )
        )
        cutoff = fields.Datetime.now() - timedelta(days=days)
        old = self.search([("ts", "<", cutoff)])
        count = len(old)
        if count:
            old.unlink()
            logger.info("Firewall event cleanup: removed %s events older than %s days.", count, days)


class FirewallAgent(models.Model):
    _name = "connect.firewall.agent"
    _description = "Firewall Service Agent (singleton)"

    name = fields.Char(default="FreeSWITCH Firewall Agent", readonly=True)
    last_seen = fields.Datetime(readonly=True)
    last_sync_at = fields.Datetime(readonly=True)
    version = fields.Char(readonly=True)
    esl_connected = fields.Boolean(readonly=True)
    bans_count = fields.Integer(readonly=True)
    authenticated_count = fields.Integer(readonly=True)
    uptime_seconds = fields.Integer(readonly=True)
    status = fields.Selection(
        [
            ("online", "Online"),
            ("stale", "Stale"),
            ("offline", "Offline"),
        ],
        compute="_compute_status",
        store=False,
    )

    @api.depends("last_seen")
    def _compute_status(self):
        now = fields.Datetime.now()
        heartbeat_interval = int(
            self.env["connect.settings"].sudo().get_param(
                "firewall_heartbeat_interval", 60
            )
        )
        for rec in self:
            if not rec.last_seen:
                rec.status = "offline"
                continue
            seconds = (now - rec.last_seen).total_seconds()
            if seconds < heartbeat_interval * 2:
                rec.status = "online"
            elif seconds < 300:
                rec.status = "stale"
            else:
                rec.status = "offline"

    @api.model
    def _get_singleton(self):
        rec = self.search([], limit=1)
        if not rec:
            rec = self.create({"name": "FreeSWITCH Firewall Agent"})
        return rec

    # ------------------------------------------------------------------
    # Outbound: notify the firewall service that state changed
    # ------------------------------------------------------------------

    @api.model
    def _trigger_sync(self, scope="all"):
        """Schedule a sync notification to the service after the commit.

        Multiple writes inside one transaction collapse into a single HTTP
        POST: postcommit callbacks dedupe by (function, args).
        """
        settings = self.env["connect.settings"].sudo()
        if not settings.get_param("firewall_enabled"):
            return
        url = settings.get_param("firewall_service_url")
        token = settings.get_param("firewall_service_token")
        if not url or not token:
            return
        sync_url = url.rstrip("/") + "/firewall/sync"

        def _send():
            try:
                requests.post(
                    sync_url,
                    json={"scope": scope},
                    headers={"Authorization": "Bearer " + token},
                    timeout=SYNC_HTTP_TIMEOUT,
                )
            except Exception as exc:
                logger.warning(
                    "Firewall sync notification to %s failed (%s); reconcile cron will retry.",
                    sync_url, exc,
                )

        self.env.cr.postcommit.add(_send)

    @api.model
    def _cron_reconcile(self):
        """Periodic safety net: tell the service to re-pull everything."""
        self._trigger_sync("all")

    @api.model
    def _service_endpoint(self, path: str) -> tuple[str, str] | tuple[None, None]:
        """Return (url, token) for a path on the firewall service, or
        (None, None) if firewall is disabled / not configured."""
        settings = self.env["connect.settings"].sudo()
        if not settings.get_param("firewall_enabled"):
            return None, None
        base = settings.get_param("firewall_service_url")
        token = settings.get_param("firewall_service_token")
        if not base or not token:
            return None, None
        return base.rstrip("/") + path, token

    @api.model
    def _call_service_unban(self, ip: str) -> tuple[bool, str]:
        """DELETE /firewall/api/bans/<ip> on the service."""
        url, token = self._service_endpoint(
            "/firewall/api/bans/" + quote(str(ip), safe="")
        )
        if not url:
            return False, _("Firewall service is not configured.")
        try:
            res = requests.delete(
                url,
                headers={"Authorization": "Bearer " + token},
                timeout=SYNC_HTTP_TIMEOUT,
            )
            if res.status_code == 200:
                self.env["connect.firewall.event"].sudo().create({
                    "event_type": "manual_unban_applied",
                    "ip": ip,
                    "details": "from event view",
                })
                return True, ""
            return False, "HTTP {}: {}".format(res.status_code, res.text[:200])
        except Exception as exc:
            return False, str(exc)

    @api.model
    def _fetch_live_banned_ips(self) -> set | None:
        """GET /firewall/api/bans on the service, return a set of IPs.
        Returns None when the service can't be reached, so callers can
        fall back to showing UI controls anyway."""
        url, token = self._service_endpoint("/firewall/api/bans")
        if not url:
            return None
        try:
            res = requests.get(
                url,
                headers={"Authorization": "Bearer " + token},
                timeout=SYNC_HTTP_TIMEOUT,
            )
            if res.status_code != 200:
                return None
            return {row["entry"] for row in res.json() if "entry" in row}
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Inbound: called by the firewall service via /freeswitch/firewall/api/*
    # controllers (Bearer-authenticated against firewall_service_token).
    # ------------------------------------------------------------------

    @api.model
    def fetch_config(self):
        """Return the firewall_* settings the service needs at boot/sync.

        The shared ``firewall_service_token`` is intentionally **not**
        returned — the service must already know it (the very same
        token authenticated this request).
        """
        settings = self.env["connect.settings"].sudo()
        keys = [
            "firewall_enabled",
            "firewall_heartbeat_interval",
            "firewall_tcp_ports",
            "firewall_udp_ports",
            "firewall_banned_timeout",
            "firewall_authenticated_timeout",
            "firewall_expire_short_timeout",
            "firewall_expire_long_timeout",
        ]
        return {k: settings.get_param(k) for k in keys}

    @api.model
    def fetch_whitelist(self):
        recs = self.env["connect.firewall.whitelist"].sudo().search(
            [("active", "=", True)]
        )
        return [
            {"id": r.id, "name": r.name, "ip_or_cidr": r.ip_or_cidr,
             "note": r.note or ""}
            for r in recs
        ]

    @api.model
    def fetch_blacklist(self):
        recs = self.env["connect.firewall.blacklist"].sudo().search(
            [("active", "=", True)]
        )
        return [
            {"id": r.id, "name": r.name, "ip_or_cidr": r.ip_or_cidr,
             "note": r.note or ""}
            for r in recs
        ]

    @api.model
    def report_event(self, payload):
        """Service reports a security event for the audit log."""
        if not isinstance(payload, dict):
            return False
        keys = {"event_type", "ip", "user_agent", "account_id", "service", "details", "ts"}
        clean = {k: v for k, v in payload.items() if k in keys and v is not None}
        if "event_type" not in clean:
            return False
        if "ts" not in clean:
            clean["ts"] = fields.Datetime.now()
        rec = self.env["connect.firewall.event"].sudo().create(clean)
        return rec.id

    @api.model
    def report_applied(self, ip=None, action=None, status="ok", message=None):
        """Service confirms an inbound sync action was applied.

        Updates last_sync_at and pushes a popup to admin users.
        """
        singleton = self.sudo()._get_singleton()
        singleton.write({"last_sync_at": fields.Datetime.now()})
        notif_type = "success" if status == "ok" else "warning"
        body = "{} {} for {}".format(
            "Applied" if status == "ok" else "Failed to apply",
            action,
            ip,
        )
        if message:
            body += " — " + message
        admin_group = self.env.ref("connect.group_admin", raise_if_not_found=False)
        if admin_group:
            for user in admin_group.sudo()[_GROUP_USERS_FIELD]:
                self.env["bus.bus"]._sendone(
                    user.partner_id,
                    "simple_notification",
                    {
                        "type": notif_type,
                        "title": "Firewall",
                        "message": body,
                        "sticky": status != "ok",
                    },
                )
        return True

    @api.model
    def report_heartbeat(self, payload):
        """Periodic heartbeat from the service.

        payload: dict with version/esl_connected/bans_count/
        authenticated_count/uptime_seconds (any subset).
        """
        singleton = self.sudo()._get_singleton()
        vals = {"last_seen": fields.Datetime.now()}
        if isinstance(payload, dict):
            for k in (
                "version",
                "esl_connected",
                "bans_count",
                "authenticated_count",
                "uptime_seconds",
            ):
                if k in payload:
                    vals[k] = payload[k]
        singleton.write(vals)
        return True
