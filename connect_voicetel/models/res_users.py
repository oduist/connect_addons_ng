# -*- coding: utf-8 -*-
import logging

from odoo import api, models

from .settings import VOICETEL_WSS_PORT

logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def get_voicetel_sip_user_config(self, user_id):
        """SIP credential and phone preferences for the VoiceTel web phone.

        Only the calling user's own configuration is ever returned: the SIP
        password is readable by its owner alone through this narrow channel
        (ADR-066 decision 5). The browser registers over WSS to the user's
        tenant SIP domain with the same credential a desk phone would use.
        """
        if user_id != self.env.user.id:
            return False
        connect_user = self.env['connect.user'].sudo().search(
            [('user', '=', user_id), ('active', '=', True)], limit=1)
        if not connect_user:
            return False
        if not (connect_user.voicetel_phone_enabled
                and connect_user.voicetel_sip_enabled
                and connect_user.voicetel_username
                and connect_user.voicetel_password
                and connect_user.voicetel_domain.domain_name):
            return False
        domain_name = connect_user.voicetel_domain.domain_name
        # Key names mirror the phone component's phone_configs contract.
        return {
            'user_config': {
                'sip_user': connect_user.voicetel_username,
                'sip_password': connect_user.voicetel_password,
                'sip_auth_user': False,
                'phone_sip_proxy': domain_name,
                'phone_realm': domain_name,
                'phone_websocket': 'wss://{}:{}'.format(domain_name, VOICETEL_WSS_PORT),
            },
            'phone_config': {
                'phone_ring_volume': connect_user.voicetel_ring_volume,
                'mask_call_number': connect_user.voicetel_mask_call_number,
                'call_popup_is_enabled': connect_user.voicetel_call_popup_is_enabled,
                'call_popup_is_sticky': connect_user.voicetel_call_popup_is_sticky,
                'record_calls': bool(connect_user.record_calls),
                'exten': connect_user.voicetel_exten_number or '',
                'outgoing_callerid': (
                    connect_user.voicetel_outgoing_callerid.number
                    or self.env['connect.voicetel.outgoing_callerid'].sudo()
                    .search([('is_default', '=', True)], limit=1).number
                    or ''
                ),
            },
        }
