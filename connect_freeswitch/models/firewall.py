# -*- coding: utf-8 -*-
import ipaddress
import logging
from datetime import timedelta

import requests

from odoo import api, fields, models
from odoo.exceptions import ValidationError

logger = logging.getLogger(__name__)

SYNC_HTTP_TIMEOUT = 3  # seconds; reconcile cron is the safety net for misses


def _validate_ip_or_cidr(value):
    if not value:
        raise ValidationError("IP address or CIDR is required.")
    try:
        ipaddress.ip_network(value, strict=False)
    except ValueError as exc:
        raise ValidationError(
            "Invalid IP or CIDR '{}': {}".format(value, exc)
        )


class FirewallWhitelist(models.Model):
    _name = "connect.firewall.whitelist"
    _description = "Firewall Whitelist Entry"
    _order = "ip_or_cidr"

    name = fields.Char(required=True, help="Short description, e.g. 'Office NY'")
    ip_or_cidr = fields.Char(
        string="IP or CIDR",
        required=True,
        help="Single IP (1.2.3.4) or CIDR network (1.2.3.0/24).",
    )
    active = fields.Boolean(default=True)
    note = fields.Text()

    @api.constrains("ip_or_cidr")
    def _check_ip_or_cidr(self):
        for rec in self:
            _validate_ip_or_cidr(rec.ip_or_cidr)
            duplicates = self.search_count([
                ("id", "!=", rec.id),
                ("ip_or_cidr", "=", rec.ip_or_cidr),
            ])
            if duplicates:
                raise ValidationError(
                    "{} is already in the whitelist.".format(rec.ip_or_cidr)
                )

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        self.env["connect.firewall.agent"]._trigger_sync("whitelist")
        return recs

    def write(self, vals):
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
        help="Single IP (1.2.3.4) or CIDR network (1.2.3.0/24).",
    )
    active = fields.Boolean(default=True)
    note = fields.Text()

    @api.constrains("ip_or_cidr")
    def _check_ip_or_cidr(self):
        for rec in self:
            _validate_ip_or_cidr(rec.ip_or_cidr)
            duplicates = self.search_count([
                ("id", "!=", rec.id),
                ("ip_or_cidr", "=", rec.ip_or_cidr),
            ])
            if duplicates:
                raise ValidationError(
                    "{} is already in the blacklist.".format(rec.ip_or_cidr)
                )

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        self.env["connect.firewall.agent"]._trigger_sync("blacklist")
        return recs

    def write(self, vals):
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
    ip = fields.Char(index=True)
    user_agent = fields.Char()
    account_id = fields.Char(
        string="Account/Extension",
        help="SIP username from the failed REGISTER/INVITE, if known.",
    )
    service = fields.Char(help="udp/tcp/ws if known.")
    details = fields.Text()
    ts = fields.Datetime(
        required=True,
        default=fields.Datetime.now,
        index=True,
        help="Timestamp from the service (not Odoo create_date).",
    )

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

    # ------------------------------------------------------------------
    # Inbound XML-RPC: called by the firewall service over the portal user
    # ------------------------------------------------------------------

    @api.model
    def fetch_config(self, *args, **kwargs):
        """Return all firewall_* settings the service needs at boot/sync.

        The ``*args`` / ``**kwargs`` swallow whatever XML-RPC clients send
        — different libraries serialise positional arguments differently
        (some inject an empty list, some don't), so we stay tolerant.
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
    def fetch_whitelist(self, *args, **kwargs):
        recs = self.env["connect.firewall.whitelist"].sudo().search(
            [("active", "=", True)]
        )
        return [{"id": r.id, "name": r.name, "ip_or_cidr": r.ip_or_cidr} for r in recs]

    @api.model
    def fetch_blacklist(self, *args, **kwargs):
        recs = self.env["connect.firewall.blacklist"].sudo().search(
            [("active", "=", True)]
        )
        return [{"id": r.id, "name": r.name, "ip_or_cidr": r.ip_or_cidr} for r in recs]

    @api.model
    def report_event(self, payload=None, *args, **kwargs):
        """Service reports a security event for the audit log.

        Some XML-RPC clients (aio_odoorpc) drop an extra positional in
        front of our payload, so we accept the dict from either the
        first positional or the first item in ``args``.
        """
        if not isinstance(payload, dict):
            for candidate in args:
                if isinstance(candidate, dict):
                    payload = candidate
                    break
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
    def report_applied(self, ip=None, action=None, status="ok", message=None,
                       *args, **kwargs):
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
            for user in admin_group.sudo().user_ids:
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
    def report_heartbeat(self, payload=None, *args, **kwargs):
        """Periodic heartbeat from the service.

        payload: dict with version/esl_connected/bans_count/
        authenticated_count/uptime_seconds (any subset).
        """
        if not isinstance(payload, dict):
            for candidate in args:
                if isinstance(candidate, dict):
                    payload = candidate
                    break
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
