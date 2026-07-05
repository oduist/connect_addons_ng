import ipaddress
import logging
import re
from odoo import fields, models, api, release
from odoo.exceptions import ValidationError
if release.version_info[0] >= 19:
    from odoo.models import Constraint

logger = logging.getLogger(__name__)


class FreeSwitchGateway(models.Model):
    _name = 'connect.freeswitch.gateway'
    _description = 'SIP Gateway'
    _order = 'name'

    name = fields.Char(required=True)
    proxy = fields.Char(required=True, help='SIP proxy address (e.g. sip.provider.com)')
    username = fields.Char()
    # Upstream SIP trunk secret. Admin-only at the field level so the
    # Connect User group and the public-webhook identity (both have model
    # read on gateways) cannot pull it over RPC — a toll-fraud vector.
    # The sofia config render reads it via sudo() (freeswitch_xml.py).
    password = fields.Char(groups="connect.group_admin")
    register = fields.Boolean(default=True)
    realm = fields.Char()
    from_domain = fields.Char()
    caller_id_in_from = fields.Boolean(help='Use caller ID in From header')
    expire_seconds = fields.Integer(default=3600)
    retry_seconds = fields.Integer(default=30)
    inbound_ips = fields.Text(
        string='Inbound IPs',
        help='IP addresses or CIDR ranges (one per line) allowed to send '
             'inbound calls without SIP authentication. '
             'Example: 185.3.68.0/24')
    active = fields.Boolean(default=True)

    if release.version_info[0] >= 19:
        _name_uniq = Constraint('UNIQUE(name)', 'Gateway name must be unique!')
    else:
        _sql_constraints = [
            ('name_uniq', 'UNIQUE(name)', 'Gateway name must be unique!'),
        ]

    @api.constrains('name')
    def _check_name(self):
        for record in self:
            if record.name and not re.match(r'^[a-zA-Z0-9_.-]+$', record.name):
                raise ValidationError(
                    "Gateway name '{}' contains invalid characters. "
                    "Only letters, digits, hyphens, underscores and dots "
                    "are allowed.".format(record.name))

    @api.constrains('inbound_ips')
    def _check_inbound_ips(self):
        for record in self:
            for line in (record.inbound_ips or '').splitlines():
                ip = line.strip()
                if not ip:
                    continue
                try:
                    ipaddress.ip_network(ip, strict=False)
                except ValueError:
                    raise ValidationError(
                        "Invalid IP address or CIDR range: '{}'".format(ip))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._reload_sofia_profile()
        if any(v.get('inbound_ips') for v in vals_list):
            self._reload_acl()
        return records

    def write(self, vals):
        result = super().write(vals)
        self._reload_sofia_profile()
        if 'inbound_ips' in vals:
            self._reload_acl()
        return result

    def unlink(self):
        has_ips = any(r.inbound_ips for r in self)
        result = super().unlink()
        self._reload_sofia_profile()
        if has_ips:
            self._reload_acl()
        return result

    def _reload_sofia_profile(self):
        """Schedule a sofia 'external' profile reload after the commit.

        The reload is deferred to post-commit so FreeSWITCH's xml_curl callback
        reads the *committed* gateway rows: a synchronous reload inside
        create()/write() races the open transaction, and the brand-new gateway
        is invisible to the separate xml_curl request (issue #38).
        """
        self.env.cr.postcommit.add(
            self.env['connect.freeswitch.gateway']._apply_sofia_profile_reload)

    @api.model
    def _apply_sofia_profile_reload(self):
        """Start the external sofia profile if it is not loaded yet, otherwise
        restart it to reload the gateway XML.

        On a fresh deployment the external profile has never been started, so a
        plain 'restart' is a silent no-op (issue #38). Detect via 'status
        profile external' and 'start' when absent; FreeSWITCH then fetches the
        now-committed gateway config via xml_curl.
        """
        Settings = self.env['connect.settings']
        status = Settings.freeswitch_api('sofia', 'status profile external')
        if not status or 'Invalid Profile' in status:
            Settings.freeswitch_api('sofia', 'profile external start')
        else:
            Settings.freeswitch_api(
                'sofia', 'profile external restart reloadxml')

    def _reload_acl(self):
        """Schedule a FreeSWITCH ACL reload after the commit, so the gateway
        IPs are visible to the separate xml_curl request (issue #38)."""
        self.env.cr.postcommit.add(
            self.env['connect.freeswitch.gateway']._apply_acl_reload)

    @api.model
    def _apply_acl_reload(self):
        """Ask FreeSWITCH to reload ACL configuration."""
        self.env['connect.settings'].freeswitch_api('reloadacl')

    @api.model
    def _get_all_acl_ips(self):
        """Return list of ACL entries from all active gateways with inbound IPs."""
        gateways = self.search([('active', '=', True), ('inbound_ips', '!=', False)])
        result = []
        for gw in gateways:
            for line in (gw.inbound_ips or '').splitlines():
                ip = line.strip()
                if ip:
                    result.append({'ip': ip, 'gateway': gw.name})
        return result

    def generate_sofia_gateway_xml(self):
        """Generate FreeSWITCH gateway XML string."""
        self.ensure_one()
        return self.env['connect.freeswitch.template'].render('config_sofia_gateway', {
            'name': self.name,
            'proxy': self.proxy,
            'username': self.username or '',
            'password': self.password or '',
            'register': 'true' if self.register else 'false',
            'realm': self.realm or '',
            'from_domain': self.from_domain or '',
            'caller_id_in_from': self.caller_id_in_from,
            'expire_seconds': str(self.expire_seconds),
            'retry_seconds': str(self.retry_seconds),
        })
