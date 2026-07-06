import logging
import re
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

    def generate_dialplan(self, params):
        """Generate outgoing route dialplan for matching routes. Returns XML string or empty string."""
        destination = params.get('Caller-Destination-Number', '')
        routes = self.sudo().search([('active', '=', True)])

        # Resolve the calling user's configured outgoing CallerID so the
        # called party sees the right number on PSTN. The directory entry
        # sets effective_caller_id_* to the extension; we override it here
        # only for the outbound leg so internal calls still show the
        # extension.
        #
        # We deliberately push only the NUMBER outwards. The display name is
        # always blanked on the trunk leg (see the template) so the outside
        # world never learns the internal caller's name. See ADR-026.
        #
        # Number resolution order: the user's own outgoing_callerid, else the
        # system-wide default DID (is_default), else nothing — in which case
        # the directory's extension stands (ADR-027, issue #96).
        cid_num = ''
        callerid = self.env['connect.freeswitch.outgoing_callerid']
        connect_user_id = params.get('variable_odoo_connect_user_id')
        if connect_user_id:
            try:
                user = self.env['connect.user'].sudo().browse(int(connect_user_id))
            except ValueError:
                user = self.env['connect.user']
            if user.exists() and user.freeswitch_outgoing_callerid:
                callerid = user.freeswitch_outgoing_callerid
        if not callerid:
            callerid = self.env['connect.freeswitch.outgoing_callerid'].sudo().search(
                [('is_default', '=', True)], limit=1)
        if callerid:
            cid_num = callerid.number or ''

        for route in routes:
            if not re.match(route.pattern, destination):
                continue

            bridge_data = self._build_bridge_data(
                route.gateway.name, destination,
                strip=route.strip, prefix=route.prefix or '')

            return self.env['connect.freeswitch.template'].render('dialplan_outgoing_route', {
                'route_id': route.id,
                'pattern': route.pattern,
                'bridge_data': bridge_data,
                'cid_num': cid_num,
            })

        return ''
