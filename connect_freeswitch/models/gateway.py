import logging
from odoo import fields, models, api, release
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
    password = fields.Char()
    register = fields.Boolean(default=True)
    realm = fields.Char()
    from_domain = fields.Char()
    caller_id_in_from = fields.Boolean(help='Use caller ID in From header')
    expire_seconds = fields.Integer(default=3600)
    retry_seconds = fields.Integer(default=30)
    active = fields.Boolean(default=True)

    if release.version_info[0] >= 19:
        _name_uniq = Constraint('UNIQUE(name)', 'Gateway name must be unique!')
    else:
        _sql_constraints = [
            ('name_uniq', 'UNIQUE(name)', 'Gateway name must be unique!'),
        ]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._reload_sofia_profile()
        return records

    def write(self, vals):
        result = super().write(vals)
        self._reload_sofia_profile()
        return result

    def unlink(self):
        result = super().unlink()
        self._reload_sofia_profile()
        return result

    def _reload_sofia_profile(self):
        """Ask FreeSWITCH to restart the external sofia profile and reload XML."""
        self.env['connect.settings'].freeswitch_api(
            'sofia', 'profile external restart reloadxml')

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
