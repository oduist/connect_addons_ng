import logging
import re
import secrets
from odoo import models, fields, api

logger = logging.getLogger(__name__)


class User(models.Model):
    _inherit = 'connect.user'

    webrtc_enabled = fields.Boolean(string='WebRTC Enabled', default=False)
    originate_ring = fields.Boolean(string='Originate Ring', default=True,
        help='Include WebRTC client when originating click-to-call calls.')
    phone_display_mode = fields.Selection(
        [('dropdown', 'Dropdown'), ('float', 'Floating Panel')],
        string='Phone Display',
        default='dropdown',
    )
    webrtc_password = fields.Char(string='WebRTC Password', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('webrtc_enabled') and not vals.get('webrtc_password'):
                vals['webrtc_password'] = secrets.token_urlsafe(16)
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('webrtc_enabled'):
            for rec in self:
                if not rec.webrtc_password and not vals.get('webrtc_password'):
                    vals['webrtc_password'] = secrets.token_urlsafe(16)
                    break
        return super().write(vals)

    def generate_dialplan(self, params, exten=None):
        """Generate FreeSWITCH dialplan to bridge to this user's endpoints."""
        self.ensure_one()
        number = exten.number if exten else self.exten_number
        if not number:
            return ''
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
