# -*- coding: utf-8 -*-
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class WebRTCController(http.Controller):
    """Controller for WebRTC/Verto client configuration."""

    @http.route('/connect/webrtc/config', type='jsonrpc', auth='user', methods=['POST'])
    def get_webrtc_config(self):
        """
        Get WebRTC configuration for the current user.
        Returns endpoint credentials and FreeSWITCH socket URL if user has
        a connect.user record with a WebRTC-enabled endpoint.
        """
        user = request.env.user
        
        connect_user = request.env['connect.user'].search([
            ('user', '=', user.id),
            ('active', '=', True)
        ], limit=1)
        
        if not connect_user:
            return {'enabled': False, 'reason': 'no_connect_user'}
        
        endpoint = request.env['connect.endpoint'].search([
            ('connect_user_id', '=', connect_user.id),
            ('webrtc_enabled', '=', True),
            ('active', '=', True)
        ], limit=1)
        
        if not endpoint:
            return {'enabled': False, 'reason': 'no_webrtc_endpoint'}
        
        socket_url = request.env['connect.settings'].get_param('freeswitch_socket_url')
        domain = request.env['connect.settings'].get_param('freeswitch_domain')

        if not socket_url:
            return {'enabled': False, 'reason': 'no_socket_url'}

        return {
            'enabled': True,
            'socketUrl': socket_url,
            'domain': domain,
            'login': endpoint.auth_user,
            'password': endpoint.auth_password,
            'callerName': connect_user.name,
            'callerNumber': connect_user.exten_number or endpoint.auth_user,
        }
