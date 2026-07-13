# -*- coding: utf-8 -*-
import logging

from odoo import api, models

logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def get_sip_user_config(self, user_id):
        """SIP credentials and phone preferences for the JsSIP web phone.

        Only the user's own configuration is ever returned — the SIP
        password is an admin-only field exposed exclusively through this
        narrow channel to the endpoint owner.
        """
        if user_id != self.env.user.id:
            return False
        connect_user = self.env['connect.user'].sudo().search(
            [('user', '=', user_id), ('active', '=', True)], limit=1)
        if not connect_user:
            return False
        endpoint = connect_user.asterisk_endpoint_ids.sudo().filtered(
            lambda e: e.asterisk_sip_transport == 'webrtc'
            and e.asterisk_sip_user and e.asterisk_sip_password)[:1]
        if not endpoint:
            return False
        # Key names mirror the phone component's phone_configs contract.
        return {
            'user_config': {
                'sip_user': endpoint.asterisk_sip_user,
                'sip_password': endpoint.asterisk_sip_password,
                'sip_auth_user': False,
            },
            'phone_config': {
                'phone_ring_volume': connect_user.phone_ring_volume,
                'mask_call_number': connect_user.mask_call_number,
                'call_popup_is_enabled': connect_user.call_popup_is_enabled,
                'call_popup_is_sticky': connect_user.call_popup_is_sticky,
            },
        }
