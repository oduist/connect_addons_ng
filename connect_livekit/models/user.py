# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, release
if release.version_info[0] >= 19:
    from odoo.models import Constraint
from odoo.exceptions import ValidationError

from livekit import api as lk_api

logger = logging.getLogger(__name__)


class User(models.Model):
    """LiveKit presence of a PBX user.

    Every field/method contributed here carries the livekit_ prefix so
    the module co-installs with the other providers on this shared
    ledger model (ADR-031/ADR-037). LiveKit has no SIP registrar, so
    there is no hardphone credential pair — only the web phone, which
    joins rooms with short-TTL JWTs.
    """
    _inherit = 'connect.user'

    originate_provider = fields.Selection(
        selection_add=[('livekit', 'LiveKit')],
        ondelete={'livekit': 'set null'},
    )
    # Enabled out of the box only when LiveKit is the sole telephony
    # module; in multi-provider databases the admin enables the LiveKit
    # web phone explicitly per user.
    livekit_client_enabled = fields.Boolean(
        'LiveKit Web Phone Enabled',
        default=lambda self: self._livekit_is_only_provider())
    livekit_exten_number = fields.Char(string='LiveKit Extension Number')
    livekit_outgoing_callerid = fields.Many2one(
        'connect.livekit.outgoing_callerid', ondelete='set null',
        string='LiveKit Outgoing CallerID')

    if release.version_info[0] >= 19:
        _livekit_exten_number_uniq = Constraint(
            'UNIQUE(livekit_exten_number)',
            'This LiveKit extension number is already used!')
    else:
        _sql_constraints = [
            ('livekit_exten_number_uniq', 'UNIQUE(livekit_exten_number)',
             'This LiveKit extension number is already used!'),
        ]

    @api.model
    def _livekit_is_only_provider(self):
        """True when connect_livekit is the only telephony module installed."""
        other = self.env['ir.module.module'].sudo().search_count([
            ('name', 'in', ['connect_twilio', 'connect_freeswitch',
                            'connect_asterisk', 'connect_telnyx']),
            ('state', '=', 'installed'),
        ])
        return not other

    @api.model
    def _pbx_number_fields(self):
        return super()._pbx_number_fields() + ['livekit_exten_number']

    @api.model
    def get_user_by_uri(self, userinfo):
        """Resolve LiveKit browser identities (user-<connect_user_id>)."""
        if isinstance(userinfo, str) and userinfo.startswith('user-'):
            try:
                user_id = int(userinfo[5:])
            except ValueError:
                user_id = False
            if user_id:
                user = self.sudo().browse(user_id)
                if user.exists():
                    return user
        return super().get_user_by_uri(userinfo)

    @api.model
    def get_livekit_phone_config(self):
        """Web phone bootstrap for the systray widget (sudo inside:
        connect_livekit models are admin-only per ADR-037)."""
        settings = self.env['connect.settings'].sudo()
        connect_user = self.env.user.connect_user
        if (not connect_user or not connect_user.sudo().livekit_client_enabled
                or not settings.get_param('livekit_ws_url')):
            return {}
        return {
            'enabled': True,
            'ws_url': settings.get_param('livekit_ws_url'),
            'identity': 'user-{}'.format(connect_user.id),
            'user_name': self.env.user.name,
        }

    @api.model
    def get_livekit_room_token(self, room_name):
        """Mint a short-TTL join token after checking the room belongs to
        a call this user takes part in. A fresh token per join replaces
        token-refresh flows."""
        user = self.env.user
        connect_user = user.connect_user
        if not connect_user or not connect_user.sudo().livekit_client_enabled:
            raise ValidationError('LiveKit web phone is not enabled!')
        if not self._livekit_user_may_join(room_name, user, connect_user):
            raise ValidationError(
                'You are not a participant of this call!')
        settings = self.env['connect.settings'].sudo()
        token = settings.livekit_create_token(
            identity='user-{}'.format(connect_user.id),
            name=user.name, room_name=room_name, ttl=600)
        return {
            'token': token,
            'ws_url': settings.get_param('livekit_ws_url'),
            'room_name': room_name,
        }

    @api.model
    def _livekit_user_may_join(self, room_name, user, connect_user):
        if not room_name:
            return False
        call = self.env['connect.call'].sudo().search(
            [('livekit_room_name', '=', room_name)], limit=1)
        if call:
            if call.caller_user == user or user in call.called_users:
                return True
            channels = call.channels
            if (connect_user in channels.mapped('caller_pbx_user')
                    or connect_user in channels.mapped('called_pbx_user')):
                return True
            return False
        # The call row may not exist yet (originate raced the webhook):
        # allow out- rooms announced to this same user over the bus is
        # not verifiable here, so fall back to meet rooms only.
        room = self.env['connect.livekit.room'].sudo().search(
            [('room_name', '=', room_name), ('state', '!=', 'finished')],
            limit=1)
        return bool(room)

    @api.model
    def livekit_hangup_room(self, room_name):
        """Terminate a call room from the web phone (deletes the LiveKit
        room, disconnecting all participants)."""
        user = self.env.user
        connect_user = user.connect_user
        if not connect_user:
            raise ValidationError('User does not have a PBX user defined!')
        if not self._livekit_user_may_join(room_name, user, connect_user):
            raise ValidationError('You are not a participant of this call!')
        try:
            self.env['connect.settings'].sudo().livekit_api_call(
                'room.delete_room',
                lk_api.DeleteRoomRequest(room=room_name))
        except ValidationError as e:
            # The room may already be gone server-side.
            logger.warning('LiveKit hangup %s: %s', room_name, e)
        return True
