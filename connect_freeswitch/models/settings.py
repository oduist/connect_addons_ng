# -*- coding: utf-8 -*-
from odoo import api, fields, models


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
            ('user_id', '=', user.id),
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

        settings = self._get_settings_record()
        socket_url = settings.freeswitch_socket_url

        if not socket_url:
            return {'enabled': False, 'reason': 'no_socket_url'}

        return {
            'enabled': True,
            'socketUrl': socket_url,
            'login': endpoint.auth_user,
            'password': endpoint.auth_password,
            'callerName': connect_user.name,
            'callerNumber': connect_user.extension or endpoint.auth_user,
        }
