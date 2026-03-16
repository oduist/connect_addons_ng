import logging
import re
from xml.etree import ElementTree as ET
from odoo import fields, models

logger = logging.getLogger(__name__)


class FreeSwitchOutgoingRoute(models.Model):
    _name = 'connect.freeswitch.outgoing_route'
    _description = 'Outgoing Route'
    _order = 'priority, id'

    name = fields.Char(required=True)
    pattern = fields.Char(required=True, help='Regex pattern for destination number (e.g. ^\\+\\d{7,}$)')
    gateway = fields.Many2one('connect.freeswitch.gateway', required=True, ondelete='restrict')
    priority = fields.Integer(default=10)
    strip = fields.Integer(default=0, help='Number of digits to strip from the beginning')
    prefix = fields.Char(help='Prefix to add after stripping')
    active = fields.Boolean(default=True)

    @classmethod
    def _build_bridge_data(cls, gateway_name, destination, strip=0, prefix=''):
        """Build bridge string with strip/prefix applied."""
        number = destination
        if strip > 0:
            number = destination[strip:]
        if prefix:
            number = prefix + number
        return 'sofia/gateway/{}/{}'.format(gateway_name, number)

    def generate_dialplan(self, context_el, params):
        """Generate outgoing route dialplan for matching routes."""
        destination = params.get('Caller-Destination-Number', '')
        routes = self.sudo().search([('active', '=', True)])

        for route in routes:
            if not re.match(route.pattern, destination):
                continue

            ext = ET.SubElement(context_el, 'extension', name='outgoing_{}'.format(route.id))
            condition = ET.SubElement(ext, 'condition',
                field='destination_number', expression=route.pattern)
            ET.SubElement(condition, 'action', application='set',
                data='odoo_call_direction=outgoing')

            bridge_data = self._build_bridge_data(
                route.gateway.name, destination,
                strip=route.strip, prefix=route.prefix or '')
            ET.SubElement(condition, 'action', application='bridge', data=bridge_data)
            return True

        return False
