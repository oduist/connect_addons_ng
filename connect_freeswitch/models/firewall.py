# -*- coding: utf-8 -*-
import ipaddress
import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

logger = logging.getLogger(__name__)


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

    _sql_constraints = [
        (
            "ip_or_cidr_unique",
            "UNIQUE(ip_or_cidr)",
            "This IP/CIDR is already in the whitelist.",
        ),
    ]

    @api.constrains("ip_or_cidr")
    def _check_ip_or_cidr(self):
        for rec in self:
            _validate_ip_or_cidr(rec.ip_or_cidr)


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

    _sql_constraints = [
        (
            "ip_or_cidr_unique",
            "UNIQUE(ip_or_cidr)",
            "This IP/CIDR is already in the blacklist.",
        ),
    ]

    @api.constrains("ip_or_cidr")
    def _check_ip_or_cidr(self):
        for rec in self:
            _validate_ip_or_cidr(rec.ip_or_cidr)


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
        cutoff = fields.Datetime.subtract(fields.Datetime.now(), days=days)
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
