import logging
import re
from odoo import models

logger = logging.getLogger(__name__)


class User(models.Model):
    _inherit = 'connect.user'

    def generate_dialplan(self, params, exten=None):
        """Generate FreeSWITCH dialplan to bridge to this user's endpoints."""
        self.ensure_one()
        number = exten.number if exten else self.exten_number or self.username
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''

        recording_url = ''
        if self.record_calls and base_url:
            recording_url = '{}freeswitch/webhook/recording'.format(
                base_url if base_url.endswith('/') else base_url + '/')

        fs_domain = self.env['connect.settings'].sudo().get_param('freeswitch_domain') or '${domain}'

        return self.env['connect.freeswitch.template'].render('dialplan_user_bridge', {
            'number': re.escape(number),
            'user_id': self.id,
            'exten_id': exten.id if exten else None,
            'record_calls': self.record_calls,
            'recording_url': recording_url,
            'fs_domain': fs_domain,
        })
