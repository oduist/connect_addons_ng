"""FreeSWITCH per-provider configuration singleton (ADR-025 / ODU-23).

Largest of the three Phase 6 migrations: 25 fields move off the flat
`connect.settings` notebook into this singleton owned by
`connect_freeswitch`. Same pattern as
`connect.provider.elevenlabs.config` (ODU-11) and
`connect.provider.twilio.config` (ODU-22).

Field-name renames (strip `freeswitch_` prefix; `firewall_` prefix is
kept because firewall is a distinct sub-system within FS):
  freeswitch_socket_url       → socket_url
  freeswitch_domain           → domain
  freeswitch_ice_servers      → ice_servers
  freeswitch_log_level        → log_level
  freeswitch_sofia_log_level  → sofia_log_level
  freeswitch_xmlrpc_host      → xmlrpc_host
  freeswitch_xmlrpc_port      → xmlrpc_port
  freeswitch_xmlrpc_user      → xmlrpc_user
  freeswitch_xmlrpc_password  → xmlrpc_password
  freeswitch_status           → status
  freeswitch_uptime           → uptime
  freeswitch_calls            → active_calls
  freeswitch_registrations    → registrations
  freeswitch_gateway_statuses → gateway_statuses
  firewall_*                  → firewall_*  (kept)
"""
import logging
import re
import xml.etree.ElementTree as ET
import xmlrpc.client

from odoo import api, fields, models
from odoo.exceptions import ValidationError

logger = logging.getLogger(__name__)

PROTECTED_FIELDS = {'display_firewall_service_token'}


class ConnectProviderFreeSwitchConfig(models.Model):
    _name = 'connect.provider.freeswitch.config'
    _description = 'FreeSWITCH Provider Configuration'

    socket_url = fields.Char(
        string='FreeSWITCH Socket URL',
        help='WebSocket URL for FreeSWITCH connection',
    )
    domain = fields.Char(
        string='FreeSWITCH Domain',
        help='SIP domain for FreeSWITCH registrations and routing.',
    )
    ice_servers = fields.Text(
        string='ICE Servers',
        default='stun:stun.l.google.com:19302\n'
                'stun:stun1.l.google.com:19302\n'
                'stun:stun.cloudflare.com:3478\n'
                'stun:stun.nextcloud.com:443',
    )
    log_level = fields.Selection(
        selection=[
            ('alert', 'ALERT'), ('crit', 'CRIT'), ('err', 'ERR'),
            ('warning', 'WARNING'), ('notice', 'NOTICE'),
            ('info', 'INFO'), ('debug', 'DEBUG'),
        ],
        string='Log Level', default='info',
    )
    sofia_log_level = fields.Selection(
        selection=[(str(i), str(i)) for i in range(10)],
        string='Sofia Log Level', default='0',
    )
    xmlrpc_host = fields.Char(string='XML-RPC Host')
    xmlrpc_port = fields.Integer(string='XML-RPC Port', default=8080)
    xmlrpc_user = fields.Char(string='XML-RPC User')
    xmlrpc_password = fields.Char(string='XML-RPC Password')

    # Status fields (populated by check_status button)
    status = fields.Char(string='Server Status', readonly=True)
    uptime = fields.Char(string='Uptime', readonly=True)
    active_calls = fields.Char(string='Active Calls', readonly=True)
    registrations = fields.Char(string='Registered Endpoints', readonly=True)
    gateway_statuses = fields.Text(string='Gateway Statuses', readonly=True)

    # Firewall sub-system
    firewall_enabled = fields.Boolean(string='Firewall Enabled', default=False)
    firewall_service_url = fields.Char(
        string='Firewall Service URL',
        default='http://host.docker.internal:8081',
    )
    firewall_service_token = fields.Char(
        string='Firewall Service Token (stored)',
        groups='connect.group_admin',
    )
    display_firewall_service_token = fields.Char(string='Firewall Service Token')
    firewall_heartbeat_interval = fields.Integer(string='Heartbeat Interval (sec)', default=60)
    firewall_event_retention_days = fields.Integer(string='Event Retention (days)', default=30)
    firewall_tcp_ports = fields.Char(string='Firewall TCP Ports', default='5060,5061,5080,5081')
    firewall_udp_ports = fields.Char(string='Firewall UDP Ports', default='5060,5061,5080,5081')
    firewall_banned_timeout = fields.Integer(string='Auto-ban TTL (sec)', default=86400)
    firewall_authenticated_timeout = fields.Integer(string='Trust TTL (sec)', default=604800)
    firewall_expire_short_timeout = fields.Integer(string='Challenge Window (sec)', default=30)
    firewall_expire_long_timeout = fields.Integer(string='Default-Deny TTL (sec)', default=86400)

    _TOKEN_MIN_LEN = 24
    _TOKEN_ALLOWED_CHARS = set(
        'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-')

    @api.model
    def _get(self):
        """Singleton accessor."""
        rec = self.sudo().search([], limit=1)
        if not rec:
            rec = self.sudo().with_context(skip_protected_fields=True).create({})
        return rec

    @api.model
    def _validate_firewall_secret(self, value):
        if value in (False, None):
            return
        value = value.strip()
        if not value:
            return
        if len(value) < self._TOKEN_MIN_LEN:
            raise ValidationError(
                f'Firewall Service Token must be at least {self._TOKEN_MIN_LEN} characters long.')
        bad = sorted({c for c in value if c not in self._TOKEN_ALLOWED_CHARS})
        if bad:
            raise ValidationError(
                "Firewall Service Token can only contain letters, digits, "
                "'_' and '-'; remove: {}".format(' '.join(bad)))

    def write(self, vals):
        if not self.env.context.get('skip_protected_fields'):
            if 'display_firewall_service_token' in vals:
                self._validate_firewall_secret(vals['display_firewall_service_token'])
        res = super().write(vals)
        # Protected-fields display masking (write the real value, mask the display)
        if not self.env.context.get('skip_protected_fields'):
            changed = {}
            for fname in PROTECTED_FIELDS:
                if vals.get(fname):
                    value = vals[fname]
                    changed[fname.replace('display_', '')] = value
                    changed[fname] = '*' * len(value)
            if changed:
                self.with_context(skip_protected_fields=True).sudo().write(changed)
        # Notify the firewall service of any firewall_* change.
        if any(k.startswith('firewall_') or k == 'display_firewall_service_token'
               for k in vals):
            self.env['connect.firewall.agent']._trigger_sync('settings')
        return res

    @api.model
    def freeswitch_api(self, command, args=''):
        """Execute a FreeSWITCH API command via mod_xml_rpc."""
        cfg = self._get().sudo()
        if not cfg.xmlrpc_host:
            logger.warning('FreeSWITCH XML-RPC host not configured')
            return False
        url = 'http://{}:{}@{}:{}/RPC2'.format(
            cfg.xmlrpc_user, cfg.xmlrpc_password,
            cfg.xmlrpc_host, cfg.xmlrpc_port or 8080,
        )
        try:
            server = xmlrpc.client.ServerProxy(url)
            result = server.freeswitch.api(command, args)
            logger.info('FreeSWITCH API %s %s: %s', command, args, result)
            return result
        except Exception as e:
            logger.error('FreeSWITCH XML-RPC error: %s', e)
            return False

    def check_status(self):
        """Fetch live status from FreeSWITCH and update display fields."""
        self.ensure_one()
        down_vals = {
            'status': 'DOWN (unreachable)',
            'uptime': '', 'active_calls': '',
            'registrations': '', 'gateway_statuses': '',
        }
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
            version_match = re.search(r'FreeSWITCH \(Version ([^)]+)\)', line)
            if version_match:
                fs_version = version_match.group(1)
        fs_status = 'UP'
        if fs_version:
            fs_status = 'UP — {}'.format(fs_version)
        fs_calls = '0'
        calls_response = self.freeswitch_api('show', 'calls count')
        if calls_response:
            m = re.search(r'(\d+)\s+total', calls_response)
            if m:
                fs_calls = m.group(1)
        fs_registrations = '0'
        reg_response = self.freeswitch_api('sofia', 'xmlstatus profile external reg')
        if reg_response and not reg_response.startswith('-ERR'):
            try:
                root = ET.fromstring(reg_response)
                regs = root.findall('.//registration')
                fs_registrations = str(len(regs))
            except ET.ParseError:
                fs_registrations = 'parse error'
        gateways = self.env['connect.freeswitch.gateway'].search([('active', '=', True)])
        status_map = {
            'REGED': 'UP (Registered)', 'NOREG': 'UP (No Registration)',
            'UNREGED': 'DOWN (Unregistered)', 'TRYING': 'TRYING',
            'FAIL_WAIT': 'DOWN (Failed)',
        }
        gateway_lines = []
        for gw in gateways:
            gw_response = self.freeswitch_api('sofia', 'xmlstatus gateway {}'.format(gw.name))
            gw_status = 'Unknown'
            if not gw_response:
                gw_status = 'Unreachable'
            elif gw_response.startswith('-ERR'):
                gw_status = 'Not loaded'
            elif gw_response.lstrip().startswith('<'):
                try:
                    gw_root = ET.fromstring(gw_response)
                    raw = gw_root.findtext('status', 'Unknown').strip()
                    gw_status = status_map.get(raw, raw)
                except ET.ParseError:
                    gw_status = 'Parse error'
            else:
                gw_status = 'Not loaded ({})'.format(gw_response.splitlines()[0].strip())
            gateway_lines.append('{}: {}'.format(gw.name, gw_status))
        self.write({
            'status': fs_status,
            'uptime': fs_uptime,
            'active_calls': fs_calls,
            'registrations': fs_registrations,
            'gateway_statuses': '\n'.join(gateway_lines) if gateway_lines else 'No active gateways',
        })

    @api.model
    def get_webrtc_config(self):
        """WebRTC config for the current user (Verto). Returns enabled=False
        with a reason when the user doesn't have a WebRTC-enabled connect.user."""
        user = self.env.user
        connect_user = self.env['connect.user'].search([
            ('user', '=', user.id),
            ('webrtc_enabled', '=', True),
            ('active', '=', True),
        ], limit=1)
        if not connect_user:
            return {'enabled': False, 'reason': 'no_webrtc_user'}
        cfg = self._get().sudo()
        if not cfg.socket_url:
            return {'enabled': False, 'reason': 'no_socket_url'}
        ice_servers = []
        for line in (cfg.ice_servers or '').splitlines():
            url = line.strip()
            if url:
                ice_servers.append({'urls': url})
        return {
            'enabled': True,
            'socketUrl': cfg.socket_url,
            'domain': cfg.domain,
            'login': user.login,
            'password': connect_user.webrtc_password,
            'callerName': connect_user.name,
            'callerNumber': connect_user.exten_number or user.login,
            'displayMode': connect_user.phone_display_mode or 'dropdown',
            'iceServers': ice_servers,
        }
