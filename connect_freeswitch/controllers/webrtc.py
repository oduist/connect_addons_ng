# -*- coding: utf-8 -*-
"""WebRTC config endpoint.

ODU-10 / ADR-023 Pillar 5: this controller no longer hard-codes FS
config. It resolves the user's active provider via
`connect.user.provider_ids` and dispatches through
`connect.provider._get_webrtc_config`. Each provider returns its
native WebRTC shape (FS: Verto creds; future Twilio: Voice JS token).

The controller lives in `connect_freeswitch` for legacy reasons (path
`/connect/webrtc/config`) — moving the path is out of scope.
"""
import logging
from odoo import http, release
from odoo.http import request

_logger = logging.getLogger(__name__)

# Odoo 19 introduced the 'jsonrpc' route type; on 18.0 the equivalent is 'json'.
_JSON_ROUTE = 'jsonrpc' if release.version_info[0] >= 19 else 'json'


class WebRTCController(http.Controller):
    """Controller for WebRTC client configuration (multi-provider)."""

    @http.route('/connect/webrtc/config', type=_JSON_ROUTE, auth='user', methods=['POST'])
    def get_webrtc_config(self):
        """Resolve the user's WebRTC-capable provider and dispatch.

        Iterates providers bound to the user (ordered by sequence) and
        returns the first non-disabled config. Falls back to the FS
        provider's impl unconditionally for backwards compatibility on
        installs that haven't populated `connect.user.provider_binding_ids`
        yet (Phase 4a is additive — ODU-7).
        """
        user_env = request.env.user
        connect_user = request.env['connect.user'].sudo().search(
            [('user', '=', user_env.id), ('active', '=', True)], limit=1,
        )
        providers = (
            connect_user.provider_ids if connect_user
            else request.env['connect.provider']
        )
        if not providers:
            providers = request.env['connect.provider'].sudo().search([])
        for provider in providers.sorted('sequence'):
            cfg = provider._get_webrtc_config(user_env)
            if cfg and cfg.get('enabled'):
                return cfg
        fs = request.env['connect.provider'].sudo().search(
            [('code', '=', 'freeswitch')], limit=1,
        )
        if fs:
            return fs._get_webrtc_config(user_env)
        return {'enabled': False, 'reason': 'no_provider_configured'}
