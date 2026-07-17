# -*- coding: utf-8 -*-
"""HTTP controller for agent bootstrap (ADR-035).

The sidecar agent pulls its runtime configuration (PBX URL, 3CX API
client credentials, recordings toggle) from here on boot, on /sync
nudges and periodically. Firewall/ADR-015 pattern: ``Authorization:
Bearer <threecx_api_key>`` checked with ``secrets.compare_digest``,
then ``sudo()`` — the route only reads admin-level configuration.
"""
import json
import logging
import secrets

from odoo import http
from odoo.http import Response, request

logger = logging.getLogger(__name__)


class ThreeCXAgentAPIController(http.Controller):

    @staticmethod
    def _check_token():
        settings = request.env['connect.settings'].sudo()
        if not settings.get_param('threecx_enabled'):
            return False
        expected = settings.get_param('threecx_api_key') or ''
        if not expected:
            return False
        auth = request.httprequest.headers.get('Authorization', '')
        if not auth.lower().startswith('bearer '):
            return False
        return secrets.compare_digest(auth[7:].strip(), expected)

    @http.route('/3cx/api/config',
                type='http', auth='none', methods=['GET'], csrf=False,
                readonly=True)
    def config(self, **_):
        if not self._check_token():
            return Response(
                json.dumps({'error': 'unauthorized'}),
                status=401,
                content_type='application/json',
                headers=[('WWW-Authenticate', 'Bearer')],
            )
        payload = request.env['connect.settings'].threecx_get_agent_config()
        return Response(
            json.dumps(payload),
            status=200,
            content_type='application/json',
        )
