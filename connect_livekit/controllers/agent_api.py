# -*- coding: utf-8 -*-
"""Bootstrap API for the oduist/livekit-agent worker.

Follows the asterisk-agent pattern (ADR-026/ADR-036):
``Authorization: Bearer <livekit_agent_token>`` checked with
``secrets.compare_digest``, then ``sudo()``.
"""
import json
import logging
import secrets

from odoo import fields, http
from odoo.http import Response, request

logger = logging.getLogger(__name__)


class LivekitAgentAPIController(http.Controller):

    @staticmethod
    def _check_token():
        expected = request.env['connect.settings'].sudo().get_param(
            'livekit_agent_token') or ''
        if not expected:
            return False
        auth = request.httprequest.headers.get('Authorization', '')
        if not auth.lower().startswith('bearer '):
            return False
        return secrets.compare_digest(auth[7:].strip(), expected)

    @staticmethod
    def _json(payload, status=200):
        return Response(
            json.dumps(payload, default=str),
            status=status,
            content_type='application/json',
        )

    @classmethod
    def _unauthorized(cls):
        return Response(
            json.dumps({'error': 'unauthorized'}),
            status=401,
            content_type='application/json',
            headers=[('WWW-Authenticate', 'Bearer')],
        )

    @http.route('/livekit/api/agent_config',
                type='http', auth='none', methods=['GET'], csrf=False)
    def agent_config(self, agent_id=None, **_):
        """Per-session agent configuration incl. tool token and AI keys."""
        if not self._check_token():
            return self._unauthorized()
        try:
            agent_id = int(agent_id)
        except (TypeError, ValueError):
            return self._json({'error': 'agent_id is required'}, status=400)
        agent = request.env['connect.livekit.agent'].sudo().browse(agent_id)
        if not agent.exists() or not agent.active:
            return self._json({'error': 'agent not found'}, status=404)
        return self._json(agent._agent_config_payload())

    @http.route('/livekit/api/heartbeat',
                type='http', auth='none', methods=['POST'], csrf=False,
                readonly=False)
    def heartbeat(self, **_):
        """Worker liveness marker shown on the Agent Worker settings page."""
        if not self._check_token():
            return self._unauthorized()
        request.env['connect.settings'].sudo().set_param(
            'livekit_worker_last_seen', fields.Datetime.to_string(
                fields.Datetime.now()))
        return self._json({'status': 'ok'})
