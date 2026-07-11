# -*- coding: utf-8 -*-
import logging

from odoo import fields, models, api

logger = logging.getLogger(__name__)


class User(models.Model):
    _inherit = 'connect.user'

    originate_provider = fields.Selection(
        selection_add=[('bird', 'Bird')],
        ondelete={'bird': 'set null'},
    )
    message_provider = fields.Selection(
        selection_add=[('bird', 'Bird')],
        ondelete={'bird': 'set null'},
    )
    # Bird has no WebRTC SDK, so click-to-call is a two-leg callback:
    # Bird dials this number first, then bridges to the destination.
    bird_phone_number = fields.Char(
        'Bird Agent Phone',
        help='E.164 number Bird dials first on click-to-call.')
    bird_voice_channel = fields.Many2one(
        'connect.bird.channel', string='Bird Voice Channel',
        ondelete='set null',
        domain="[('platform_id', '=', 'voice')]")
    bird_message_channel = fields.Many2one(
        'connect.bird.channel', string='Bird Message Channel',
        ondelete='set null',
        domain="[('platform_id', 'in', ('sms', 'whatsapp'))]",
        help='Default sender channel for outgoing messages.')

    @api.model
    def _pbx_number_fields(self):
        return super()._pbx_number_fields() + ['bird_phone_number']

    @api.model
    def get_user_by_bird_number(self, number):
        """connect.user whose agent phone matches a Bird call leg number."""
        if not number:
            return self.env['connect.user']
        return self.sudo().search(
            [('bird_phone_number', '=', number)], limit=1)
