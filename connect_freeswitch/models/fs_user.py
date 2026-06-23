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

    def _get_verto_login(self):
        """Return the Verto JSON-RPC login for this user's res.users.

        Format: ``<login-local-part><res.users.id>`` (e.g. ``litnimax42``).
        Built from the local part of ``res.users.login`` (the slice before
        ``@``) concatenated with the numeric user id. Guaranteed not to
        contain ``@`` (mod_verto splits the login string on ``@`` to derive
        the SIP realm). See specs/decisions/016-verto-login-uses-user-id.md.
        """
        self.ensure_one()
        if not self.user:
            return ''
        local = (self.user.login or '').split('@', 1)[0] or 'user'
        return '{}{}'.format(local, self.user.id)

    @api.model
    def _resolve_verto_login(self, login_str):
        """Reverse of ``_get_verto_login``: find res.users by the Verto login.

        Splits the string into ``<local><id>`` where ``<id>`` is the longest
        run of trailing digits, then verifies the local part matches
        ``user.login.split('@')[0]``. Returns an empty ``res.users`` recordset
        on miss.
        """
        if not login_str:
            return self.env['res.users']
        m = re.match(r'^(.+?)(\d+)$', login_str)
        if not m:
            return self.env['res.users']
        local, uid = m.group(1), int(m.group(2))
        user = self.env['res.users'].sudo().browse(uid).exists()
        if not user:
            return self.env['res.users']
        expected = (user.login or '').split('@', 1)[0] or 'user'
        if local != expected:
            return self.env['res.users']
        return user

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
