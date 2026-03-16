# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.addons.connect.models.license import ODUIST_MODULES

ODUIST_MODULES.append('connect_freeswitch')


class Settings(models.Model):
    _inherit = "connect.settings"

    freeswitch_socket_url = fields.Char(
        string="FreeSWITCH Socket URL",
        help="WebSocket URL for FreeSWITCH connection",
    )

    @api.model
    def get_webrtc_config(self):
        """
        Get WebRTC configuration for the current user.
        Returns endpoint credentials and FreeSWITCH socket URL if user has
        a connect.user record with a WebRTC-enabled endpoint.
        """
        user = self.env.user

        connect_user = self.env['connect.user'].search([
            ('user', '=', user.id),
            ('active', '=', True)
        ], limit=1)

        if not connect_user:
            return {'enabled': False, 'reason': 'no_connect_user'}

        endpoint = self.env['connect.endpoint'].search([
            ('connect_user_id', '=', connect_user.id),
            ('webrtc_enabled', '=', True),
            ('active', '=', True)
        ], limit=1)

        if not endpoint:
            return {'enabled': False, 'reason': 'no_webrtc_endpoint'}

        socket_url = self.get_param('freeswitch_socket_url')

        if not socket_url:
            return {'enabled': False, 'reason': 'no_socket_url'}

        return {
            'enabled': True,
            'socketUrl': socket_url,
            'login': endpoint.auth_user,
            'password': endpoint.auth_password,
            'callerName': connect_user.name,
            'callerNumber': connect_user.exten_number or endpoint.auth_user,
        }
