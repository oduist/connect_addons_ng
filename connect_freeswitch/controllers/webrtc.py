# -*- coding: utf-8 -*-
import logging
from odoo import http, release
from odoo.http import request

_logger = logging.getLogger(__name__)

# Odoo 19 introduced the 'jsonrpc' route type; on 18.0 the equivalent is 'json'.
_JSON_ROUTE = 'jsonrpc' if release.version_info[0] >= 19 else 'json'


class WebRTCController(http.Controller):
    """Controller for WebRTC/Verto client configuration."""

    @http.route('/connect/webrtc/config', type=_JSON_ROUTE, auth='user', methods=['POST'])
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

        # Verto login = <login-local-part><res.users.id> (e.g. "litnimax42").
        # Strips '@' (mod_verto splits on '@' to derive the realm) and stays
        # unique across users that share an email local part. See
        # specs/decisions/016-verto-login-uses-user-id.md.
        #
        # Rotate the WebRTC password on issuance, same as
        # connect.settings.get_webrtc_config (the path the current JS uses), so
        # this parallel route never hands out a stale, non-rotating password.
        # See ADR-022.
        password = connect_user._rotate_webrtc_password()
        return {
            'enabled': True,
            'socketUrl': socket_url,
            'domain': domain,
            'login': connect_user._get_verto_login(),
            'password': password,
            'callerName': connect_user.name,
            'callerNumber': connect_user.exten_number or user.login,
        }
