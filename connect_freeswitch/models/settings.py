# -*- coding: utf-8 -*-
import logging
import re
import xml.etree.ElementTree as ET
import xmlrpc.client

from odoo import api, fields, models
from odoo.addons.connect.models.license import ODUIST_MODULES
from odoo.addons.connect.models.settings import PROTECTED_FIELDS

ODUIST_MODULES.append('connect_freeswitch')

# Mask the firewall secrets the same way the core module masks openai_api_key.
for _field in ("display_firewall_service_token", "display_freeswitch_agent_password"):
    if _field not in PROTECTED_FIELDS:
        PROTECTED_FIELDS.append(_field)

logger = logging.getLogger(__name__)


class Settings(models.Model):
    _inherit = "connect.settings"

    freeswitch_socket_url = fields.Char(
        string="FreeSWITCH Socket URL",
        help="WebSocket URL for FreeSWITCH connection",
    )
    freeswitch_domain = fields.Char(
        string="FreeSWITCH Domain",
        help="SIP domain for FreeSWITCH registrations and routing. "
             "Used in sofia profile (force-register-domain) and directory XML.",
    )
    freeswitch_ice_servers = fields.Text(
        string="ICE Servers",
        default="stun:stun.l.google.com:19302\n"
                "stun:stun1.l.google.com:19302\n"
                "stun:stun.cloudflare.com:3478\n"
                "stun:stun.nextcloud.com:443",
        help="STUN/TURN server URIs for WebRTC, one per line. "
             "Example: stun:stun.example.com:3478 or "
             "turn:turn.example.com:3478?transport=udp",
    )
    freeswitch_log_level = fields.Selection(
        selection=[
            ('alert', 'ALERT'),
            ('crit', 'CRIT'),
            ('err', 'ERR'),
            ('warning', 'WARNING'),
            ('notice', 'NOTICE'),
            ('info', 'INFO'),
            ('debug', 'DEBUG'),
        ],
        string="Log Level",
        default='info',
        help="FreeSWITCH core and console log level. "
             "Pass as FS_LOG_LEVEL env var to the container.",
    )
    freeswitch_sofia_log_level = fields.Selection(
        selection=[
            ('0', '0 - Minimal'),
            ('1', '1'),
            ('2', '2'),
            ('3', '3'),
            ('4', '4'),
            ('5', '5'),
            ('6', '6'),
            ('7', '7'),
            ('8', '8'),
            ('9', '9 - Maximum'),
        ],
        string="Sofia Log Level",
        default='0',
        help="Sofia SIP module log verbosity (0-9). "
             "Pass as FS_SOFIA_LOG_LEVEL env var to the container.",
    )
    freeswitch_xmlrpc_host = fields.Char(
        string="XML-RPC Host",
        help="FreeSWITCH XML-RPC host (e.g. fs.example.com)",
    )
    freeswitch_xmlrpc_port = fields.Integer(
        string="XML-RPC Port",
        default=8080,
        help="FreeSWITCH mod_xml_rpc port (default: 8080)",
    )
    freeswitch_xmlrpc_user = fields.Char(
        string="XML-RPC User",
        help="FreeSWITCH mod_xml_rpc username",
    )
    freeswitch_xmlrpc_password = fields.Char(
        string="XML-RPC Password",
        help="FreeSWITCH mod_xml_rpc password",
    )

    # Status fields (populated by check_freeswitch_status button)
    freeswitch_status = fields.Char(string="Server Status", readonly=True)
    freeswitch_uptime = fields.Char(string="Uptime", readonly=True)
    freeswitch_calls = fields.Char(string="Active Calls", readonly=True)
    freeswitch_registrations = fields.Char(string="Registered Endpoints", readonly=True)
    freeswitch_gateway_statuses = fields.Text(string="Gateway Statuses", readonly=True)

    # Firewall settings
    firewall_enabled = fields.Boolean(
        string="Firewall Enabled",
        default=False,
        help="Enable the FreeSWITCH firewall service for SIP brute-force protection.",
    )
    firewall_service_url = fields.Char(
        string="Firewall Service URL",
        default="http://host.docker.internal:8081",
        help="Base URL of the firewall service. Odoo posts sync notifications "
             "to <url>/firewall/sync. For Docker hosts, use host.docker.internal; "
             "otherwise the LAN IP of the host where the service container runs.",
    )
    firewall_service_token = fields.Char(
        string="Firewall Service Token (stored)",
        groups="connect.group_admin",
    )
    display_firewall_service_token = fields.Char(
        string="Firewall Service Token",
        help="Shared secret used by Odoo and the firewall service to "
             "authenticate each other. Set the same value in the AGENT_TOKEN "
             "env var of the service. Visible only to administrators.",
    )
    freeswitch_agent_password = fields.Char(
        string="FreeSWITCH Agent Password (stored)",
        groups="connect.group_admin",
    )
    display_freeswitch_agent_password = fields.Char(
        string="FreeSWITCH Agent Password",
        help="Password for the freeswitch_agent portal user. The firewall "
             "service and future FreeSWITCH-side automation log in to Odoo "
             "with it. Set the same value in the ODOO_PASSWORD env var.",
    )
    firewall_heartbeat_interval = fields.Integer(
        string="Heartbeat Interval (sec)",
        default=60,
        help="How often the firewall service reports its status to Odoo.",
    )
    firewall_event_retention_days = fields.Integer(
        string="Event Retention (days)",
        default=30,
        help="How long firewall security events are kept in the database.",
    )
    firewall_tcp_ports = fields.Char(
        string="Firewall TCP Ports",
        default="5060,5061,5080,5081",
        help="Comma-separated TCP ports to protect (SIP, SIPS, WSS).",
    )
    firewall_udp_ports = fields.Char(
        string="Firewall UDP Ports",
        default="5060,5061,5080,5081",
        help="Comma-separated UDP ports to protect (SIP).",
    )
    firewall_banned_timeout = fields.Integer(
        string="Auto-ban TTL (sec)",
        default=86400,
        help="How long an automatically banned IP stays in the banned ipset.",
    )
    firewall_authenticated_timeout = fields.Integer(
        string="Trust TTL (sec)",
        default=604800,
        help="How long an IP stays trusted after a successful authentication.",
    )
    firewall_expire_short_timeout = fields.Integer(
        string="Challenge Window (sec)",
        default=30,
        help="Time given to a new IP to respond to a SIP 401 challenge.",
    )
    firewall_expire_long_timeout = fields.Integer(
        string="Default-Deny TTL (sec)",
        default=86400,
        help="Default-deny duration after a challenge is sent but not answered.",
    )

    _TOKEN_MIN_LEN = 24
    _TOKEN_ALLOWED_CHARS = set(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
    )
    _PASSWORD_MIN_LEN = 12

    @api.model
    def _validate_firewall_secret(self, kind, value):
        """Raise ValidationError on weak / malformed secrets."""
        from odoo.exceptions import ValidationError
        if value in (False, None):
            return
        value = value.strip()
        if not value:
            return
        if kind == "token":
            if len(value) < self._TOKEN_MIN_LEN:
                raise ValidationError(
                    "Firewall Service Token must be at least {} characters long.".format(
                        self._TOKEN_MIN_LEN
                    )
                )
            bad = sorted({c for c in value if c not in self._TOKEN_ALLOWED_CHARS})
            if bad:
                raise ValidationError(
                    "Firewall Service Token can only contain letters, digits, '_' and '-'; "
                    "remove: {}".format(" ".join(bad))
                )
        elif kind == "password":
            if len(value) < self._PASSWORD_MIN_LEN:
                raise ValidationError(
                    "FreeSWITCH Agent Password must be at least {} characters long.".format(
                        self._PASSWORD_MIN_LEN
                    )
                )
            if any(c.isspace() or ord(c) < 32 for c in value):
                raise ValidationError(
                    "FreeSWITCH Agent Password cannot contain spaces or control characters."
                )

    def action_generate_firewall_token(self):
        """Generate a fresh URL-safe Firewall Service Token."""
        import secrets
        self.ensure_one()
        self.sudo().write({"display_firewall_service_token": secrets.token_urlsafe(32)})
        return True

    def action_generate_agent_password(self):
        """Generate a fresh password for the freeswitch_agent portal user."""
        import secrets
        self.ensure_one()
        self.sudo().write({"display_freeswitch_agent_password": secrets.token_urlsafe(24)})
        return True

    def write(self, vals):
        # The core settings.write() does a second-pass write under the
        # 'skip_protected_fields' context to replace the displayed
        # secret with asterisks. Skip our validation in that pass so we
        # don't reject the masked value.
        if not self.env.context.get("skip_protected_fields"):
            if "display_firewall_service_token" in vals:
                self._validate_firewall_secret(
                    "token", vals["display_firewall_service_token"]
                )
            if "display_freeswitch_agent_password" in vals:
                self._validate_firewall_secret(
                    "password", vals["display_freeswitch_agent_password"]
                )
        # When an admin updates the agent password, propagate it to the
        # portal user record so XML-RPC login works with the new value.
        new_password = vals.get("display_freeswitch_agent_password")
        res = super().write(vals)
        if new_password:
            user = self.env.ref(
                "connect_freeswitch.user_freeswitch_agent",
                raise_if_not_found=False,
            )
            if user:
                user.sudo().write({"password": new_password})
        # Notify the firewall service that settings changed.
        if any(k.startswith("firewall_") or k == "display_firewall_service_token"
               for k in vals):
            self.env["connect.firewall.agent"]._trigger_sync("settings")
        return res

    @api.model
    def freeswitch_api(self, command, args=''):
        """Execute a FreeSWITCH API command via mod_xml_rpc.

        Returns the command response string, or False on failure.
        Errors are logged but never raised to avoid blocking callers.
        """
        host = self.get_param('freeswitch_xmlrpc_host')
        port = self.get_param('freeswitch_xmlrpc_port') or 8080
        user = self.get_param('freeswitch_xmlrpc_user')
        password = self.sudo().get_param('freeswitch_xmlrpc_password')
        if not host:
            logger.warning("FreeSWITCH XML-RPC host not configured")
            return False
        url = "http://{}:{}@{}:{}/RPC2".format(user, password, host, port)
        try:
            server = xmlrpc.client.ServerProxy(url)
            result = server.freeswitch.api(command, args)
            logger.info("FreeSWITCH API %s %s: %s", command, args, result)
            return result
        except Exception as e:
            logger.error("FreeSWITCH XML-RPC error: %s", e)
            return False

    def check_freeswitch_status(self):
        """Fetch live status from FreeSWITCH and update display fields."""
        self.ensure_one()
        down_vals = {
            'freeswitch_status': 'DOWN (unreachable)',
            'freeswitch_uptime': '',
            'freeswitch_calls': '',
            'freeswitch_registrations': '',
            'freeswitch_gateway_statuses': '',
        }

        # 1. Basic status
        status_response = self.freeswitch_api('status')
        if not status_response:
            self.write(down_vals)
            return

        fs_version = ''
        fs_uptime = ''
        for line in status_response.splitlines():
            line = line.strip()
            if line.startswith('UP '):
                fs_uptime = line[3:]
            version_match = re.search(
                r'FreeSWITCH \(Version ([^)]+)\)', line)
            if version_match:
                fs_version = version_match.group(1)

        fs_status = 'UP'
        if fs_version:
            fs_status = 'UP — {}'.format(fs_version)

        # 2. Active calls
        fs_calls = '0'
        calls_response = self.freeswitch_api('show', 'calls count')
        if calls_response:
            m = re.search(r'(\d+)\s+total', calls_response)
            if m:
                fs_calls = m.group(1)

        # 3. Registered endpoints
        fs_registrations = '0'
        reg_response = self.freeswitch_api(
            'sofia', 'xmlstatus profile external reg')
        if reg_response and not reg_response.startswith('-ERR'):
            try:
                root = ET.fromstring(reg_response)
                regs = root.findall('.//registration')
                fs_registrations = str(len(regs))
            except ET.ParseError:
                fs_registrations = 'parse error'

        # 4. Gateway statuses
        gateways = self.env['connect.freeswitch.gateway'].search(
            [('active', '=', True)])
        status_map = {
            'REGED': 'UP (Registered)',
            'NOREG': 'UP (No Registration)',
            'UNREGED': 'DOWN (Unregistered)',
            'TRYING': 'TRYING',
            'FAIL_WAIT': 'DOWN (Failed)',
        }
        gateway_lines = []
        for gw in gateways:
            gw_response = self.freeswitch_api(
                'sofia', 'xmlstatus gateway {}'.format(gw.name))
            gw_status = 'Unknown'
            if gw_response and not gw_response.startswith('-ERR'):
                try:
                    gw_root = ET.fromstring(gw_response)
                    raw = gw_root.findtext('status', 'Unknown').strip()
                    gw_status = status_map.get(raw, raw)
                except ET.ParseError:
                    gw_status = 'Parse error'
            elif gw_response and gw_response.startswith('-ERR'):
                gw_status = 'Not found in sofia'
            else:
                gw_status = 'Unreachable'
            gateway_lines.append('{}: {}'.format(gw.name, gw_status))

        self.write({
            'freeswitch_status': fs_status,
            'freeswitch_uptime': fs_uptime,
            'freeswitch_calls': fs_calls,
            'freeswitch_registrations': fs_registrations,
            'freeswitch_gateway_statuses': '\n'.join(gateway_lines)
            if gateway_lines else 'No active gateways',
        })

    @api.model
    def get_webrtc_config(self):
        """
        Get WebRTC configuration for the current user.
        Returns credentials and FreeSWITCH socket URL if user has
        a connect.user record with WebRTC enabled.
        """
        user = self.env.user

        connect_user = self.env['connect.user'].search([
            ('user', '=', user.id),
            ('webrtc_enabled', '=', True),
            ('active', '=', True)
        ], limit=1)

        if not connect_user:
            return {'enabled': False, 'reason': 'no_webrtc_user'}

        socket_url = self.get_param('freeswitch_socket_url')
        domain = self.get_param('freeswitch_domain')

        if not socket_url:
            return {'enabled': False, 'reason': 'no_socket_url'}

        ice_servers_text = self.get_param('freeswitch_ice_servers') or ''
        ice_servers = []
        for line in ice_servers_text.splitlines():
            url = line.strip()
            if url:
                ice_servers.append({'urls': url})

        return {
            'enabled': True,
            'socketUrl': socket_url,
            'domain': domain,
            'login': user.login,
            'password': connect_user.webrtc_password,
            'callerName': connect_user.name,
            'callerNumber': connect_user.exten_number or user.login,
            'displayMode': connect_user.phone_display_mode or 'dropdown',
            'iceServers': ice_servers,
        }
