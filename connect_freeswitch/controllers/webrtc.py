# -*- coding: utf-8 -*-
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class WebRTCController(http.Controller):
    """Controller for WebRTC/Verto client configuration."""

    @http.route('/connect/webrtc/config', type='json', auth='user', methods=['POST'])
    def get_webrtc_config(self):
        """
        Get WebRTC configuration for the current user.
        Returns credentials and FreeSWITCH socket URL if user has
        a connect.user record with WebRTC enabled.
        """
        user = request.env.user

        connect_user = request.env['connect.user'].search([
            ('user', '=', user.id),
            ('webrtc_enabled', '=', True),
            ('active', '=', True)
        ], limit=1)

        if not connect_user:
            return {'enabled': False, 'reason': 'no_webrtc_user'}

        socket_url = request.env['connect.settings'].get_param('freeswitch_socket_url')
        domain = request.env['connect.settings'].get_param('freeswitch_domain')

        if not socket_url:
            return {'enabled': False, 'reason': 'no_socket_url'}

        # The Verto login MUST NOT contain '@' (mod_verto splits on '@' to
        # derive the realm). Use the numeric res.users.id; the FS XML
        # directory matches the same id. See
        # specs/decisions/014-verto-login-uses-user-id.md.
        return {
            'enabled': True,
            'socketUrl': socket_url,
            'domain': domain,
            'login': str(user.id),
            'password': connect_user.webrtc_password,
            'callerName': connect_user.name,
            'callerNumber': connect_user.exten_number or user.login,
        }
