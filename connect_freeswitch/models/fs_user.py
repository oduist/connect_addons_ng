import logging
import re
import secrets
from odoo import models, fields, api

logger = logging.getLogger(__name__)


class User(models.Model):
    _inherit = 'connect.user'

    originate_provider = fields.Selection(
        selection_add=[('freeswitch', 'FreeSWITCH')],
        ondelete={'freeswitch': 'set null'},
    )
    freeswitch_exten = fields.Many2one(
        'connect.freeswitch.exten', ondelete='set null', readonly=True,
        string='FreeSWITCH Extension')
    freeswitch_exten_number = fields.Char(
        related='freeswitch_exten.number', store=True)
    freeswitch_outgoing_callerid = fields.Many2one(
        'connect.freeswitch.outgoing_callerid', ondelete='set null',
        string='FreeSWITCH Outgoing CallerID')
    freeswitch_endpoint_ids = fields.One2many(
        'connect.freeswitch.endpoint', 'connect_user_id', string='FreeSWITCH Endpoints')
    freeswitch_endpoint_count = fields.Integer(compute='_compute_freeswitch_endpoint_count')
    webrtc_enabled = fields.Boolean(string='WebRTC Enabled', default=False)

    def _compute_freeswitch_endpoint_count(self):
        for rec in self:
            rec.freeswitch_endpoint_count = len(rec.freeswitch_endpoint_ids)

    @api.model
    def _pbx_number_fields(self):
        return super()._pbx_number_fields() + ['freeswitch_exten_number']

    def create_freeswitch_extension(self):
        self.ensure_one()
        return self.env['connect.freeswitch.exten'].create_extension(
            self, 'connect.user', current_exten=self.freeswitch_exten)
    originate_ring = fields.Boolean(string='Originate Ring', default=True,
        help='Include WebRTC client when originating click-to-call calls.')
    phone_display_mode = fields.Selection(
        [('dropdown', 'Dropdown'), ('float', 'Floating Panel')],
        string='Phone Display',
        default='dropdown',
    )
    # Field-level groups keep the webhook identity (which has model read
    # on connect.user for the FS directory render) from pulling WebRTC
    # secrets over plain ORM; the directory render and get_webrtc_config
    # reach it via sudo / the own-record rule. The owning user still reads
    # their own credential for the softphone.
    webrtc_password = fields.Char(
        string='WebRTC Password', readonly=True,
        groups="connect.group_admin,connect.group_user")

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

    def _rotate_webrtc_password(self):
        """Generate, store and broadcast a fresh WebRTC/Verto password.

        Called at credential-issuance time (``get_webrtc_config``) so the
        delivered value equals the value FreeSWITCH checks via ``/freeswitch/xml``
        equals the value the JS client sends. A previously leaked password is
        invalidated the next time the softphone fetches its config. FreeSWITCH
        re-authenticates every Verto registration live against the DB value, so
        no FS reload is needed (see issue #36, ADR-026).

        ``sudo()``: ``webrtc_password`` is readonly and ``group_user`` has
        ``perm_write=False`` on ``connect.user``; ``get_webrtc_config`` runs as
        the logged-in (non-admin) user.

        Broadcasts the new credentials to the user's *private* bus channel so
        other open tabs of the same user update their Verto client password in
        place (no forced re-register; active calls survive).
        """
        self.ensure_one()
        new_password = secrets.token_urlsafe(16)
        self.sudo().write({'webrtc_password': new_password})
        if self.user:
            # Private per-user target — NOT the shared 'connect_actions' string
            # channel, which is global and would leak the secret to other users.
            self.env['bus.bus']._sendone(
                self.user.partner_id,
                'connect_freeswitch.verto_credentials',
                {'login': self._get_verto_login(), 'password': new_password},
            )
        return new_password

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
        number = exten.number if exten else self.freeswitch_exten_number
        if not number:
            return ''

        recording_url = ''
        if self.record_calls:
            recording_url = self.env['connect.settings'].get_recording_webhook_url()

        fs_domain = self.env['connect.settings'].sudo().get_param('freeswitch_domain') or '${domain}'

        return self.env['connect.freeswitch.template'].render('dialplan_user_bridge', {
            'number': re.escape(number),
            'user_id': self.id,
            'exten_id': exten.id if exten else None,
            'record_calls': self.record_calls,
            'recording_url': recording_url,
            'fs_domain': fs_domain,
        })
