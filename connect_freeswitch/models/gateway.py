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

    def generate_sofia_gateway_xml(self, parent_el):
        """Generate FreeSWITCH gateway XML element."""
        from xml.etree import ElementTree as ET
        self.ensure_one()
        gw = ET.SubElement(parent_el, 'gateway', name=self.name)
        ET.SubElement(gw, 'param', name='proxy', value=self.proxy)
        if self.username:
            ET.SubElement(gw, 'param', name='username', value=self.username)
        if self.password:
            ET.SubElement(gw, 'param', name='password', value=self.password)
        ET.SubElement(gw, 'param', name='register', value='true' if self.register else 'false')
        if self.realm:
            ET.SubElement(gw, 'param', name='realm', value=self.realm)
        if self.from_domain:
            ET.SubElement(gw, 'param', name='from-domain', value=self.from_domain)
        if self.caller_id_in_from:
            ET.SubElement(gw, 'param', name='caller-id-in-from', value='true')
        ET.SubElement(gw, 'param', name='expire-seconds', value=str(self.expire_seconds))
        ET.SubElement(gw, 'param', name='retry-seconds', value=str(self.retry_seconds))
        return gw
