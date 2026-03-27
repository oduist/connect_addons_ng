# -*- coding: utf-8 -*-
import logging
import re
import xml.etree.ElementTree as ET
import xmlrpc.client

from odoo import api, fields, models
from odoo.addons.connect.models.license import ODUIST_MODULES

ODUIST_MODULES.append('connect_freeswitch')

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
        Returns endpoint credentials and FreeSWITCH socket URL if user has
        a connect.user record with a WebRTC-enabled endpoint.
        """
        user = self.env.user

        connect_user = self.env['connect.user'].search([
            ('user', '=', user.id),
            ('active', '=', True)
        ], limit=1)

        if not connect_user:
            return {'enabled': False, 'reason': 'no_connect_user'}

        endpoint = self.env['connect.endpoint'].search([
            ('connect_user_id', '=', connect_user.id),
            ('webrtc_enabled', '=', True),
            ('active', '=', True)
        ], limit=1)

        if not endpoint:
            return {'enabled': False, 'reason': 'no_webrtc_endpoint'}

        socket_url = self.get_param('freeswitch_socket_url')
        domain = self.get_param('freeswitch_domain')

        if not socket_url:
            return {'enabled': False, 'reason': 'no_socket_url'}

        return {
            'enabled': True,
            'socketUrl': socket_url,
            'domain': domain,
            'login': endpoint.auth_user,
            'password': endpoint.auth_password,
            'callerName': connect_user.name,
            'callerNumber': connect_user.exten_number or endpoint.auth_user,
        }
