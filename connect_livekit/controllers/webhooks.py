# -*- coding: utf-8 -*-
"""LiveKit webhook and sidecar upload controllers.

/livekit/webhook receives the LiveKit server webhooks (JWT in the
Authorization header, signed with the API key/secret) and dispatches to
the ledger under the core webhook user. /livekit/webhook/recording/*
receives egress files from the uploader sidecar authenticated with
``Authorization: Bearer <livekit_agent_token>`` (the asterisk-agent
pattern, ADR-036).
"""
import base64
import hmac
import json
import logging
import secrets

from odoo import http
from odoo.http import Response, request
from odoo.exceptions import ValidationError

from livekit import api as lk_api

logger = logging.getLogger(__name__)

MAX_RECORDING_UPLOAD_BYTES = 512 * 1024 * 1024
MAX_AI_WEBHOOK_BYTES = 64 * 1024
# Transcripts of long conversations are bigger than tool calls.
MAX_AI_TRANSCRIPT_BYTES = 2 * 1024 * 1024


class LivekitWebhooksController(http.Controller):

    @staticmethod
    def _verify_webhook():
        """Verify the LiveKit webhook JWT over the raw body."""
        settings = request.env['connect.settings'].sudo()
        if not settings.get_param('livekit_verify_webhooks'):
            return True
        api_key = settings.get_param('livekit_api_key')
        api_secret = settings.get_param('livekit_api_secret')
        if not api_key or not api_secret:
            logger.error('LiveKit API key/secret are not configured!')
            return False
        auth_header = request.httprequest.headers.get('Authorization', '')
        body = request.httprequest.get_data(as_text=True)
        try:
            lk_api.WebhookReceiver(
                lk_api.TokenVerifier(api_key, api_secret)
            ).receive(body, auth_header)
            return True
        except Exception as e:
            logger.error('LiveKit webhook verification failed: %s', e)
            return False

    @staticmethod
    def _check_agent_token():
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

    @http.route('/livekit/webhook', methods=['POST'], type='http',
                auth='public', csrf=False)
    def livekit_webhook(self, **kw):
        if not self._verify_webhook():
            return self._json({'error': 'invalid signature'}, status=403)
        try:
            event = json.loads(
                request.httprequest.get_data(as_text=True) or '{}')
        except ValueError:
            return self._json({'error': 'invalid body'}, status=400)
        request.env['connect.call'].with_user(
            request.env.ref('connect.user_connect_webhook')
        ).on_livekit_webhook(event)
        return self._json({'status': 'ok'})

    @http.route('/livekit/webhook/recording/<string:filename>',
                type='http', auth='none', methods=['PUT', 'POST'],
                csrf=False, readonly=False)
    def recording_upload(self, filename, **_):
        """Receive an egress file from the uploader sidecar.

        The upload may arrive before or after egress_ended — both orders
        are safe (livekit_store_recording_file merges by filename).
        """
        if not self._check_agent_token():
            return self._unauthorized()
        file_data = request.httprequest.get_data()
        if not file_data:
            return Response('No file data', status=400)
        if len(file_data) > MAX_RECORDING_UPLOAD_BYTES:
            return Response('File too large', status=413)
        webhook_user = request.env.ref('connect.user_connect_webhook')
        rec_id = request.env['connect.recording'].with_user(
            webhook_user.id
        ).livekit_store_recording_file(
            filename, base64.b64encode(file_data))
        return self._json({'status': 'ok', 'recording_id': rec_id})

    # ------------------------------------------------------------------
    # AI agent webhooks: authenticated by the per-agent tool token
    # (X-Odoo-LiveKit-Token header, the Telnyx AI pattern).
    # ------------------------------------------------------------------

    @staticmethod
    def _get_agent_checked(agent_id):
        agent = request.env['connect.livekit.agent'].sudo().browse(agent_id)
        if not agent.exists():
            return None
        token = request.httprequest.headers.get('X-Odoo-LiveKit-Token', '')
        expected = agent.tool_token or ''
        if not expected or not hmac.compare_digest(token, expected):
            return None
        return agent

    @classmethod
    def _read_ai_payload(cls, max_bytes=MAX_AI_WEBHOOK_BYTES):
        body = request.httprequest.get_data()
        if len(body) > max_bytes:
            return None, cls._json({'error': 'payload too large'}, status=413)
        try:
            payload = json.loads(body or b'{}')
        except ValueError:
            return None, cls._json({'error': 'invalid body'}, status=400)
        if not isinstance(payload, dict):
            return None, cls._json({'error': 'invalid body'}, status=400)
        return payload, None

    @http.route('/livekit/webhook/agent/<int:agent_id>/tool/<string:tool_name>',
                methods=['POST'], type='http', auth='public', csrf=False)
    def agent_tool(self, agent_id, tool_name, **kw):
        agent = self._get_agent_checked(agent_id)
        if not agent:
            return self._json({'error': 'unauthorized'}, status=403)
        payload, error = self._read_ai_payload()
        if error:
            return error
        channel_sid = payload.pop('channel_sid', None)
        try:
            result = agent.execute_tool(tool_name, payload, channel_sid)
        except ValidationError as e:
            return self._json({'ok': False, 'error': str(e)}, status=400)
        return self._json(result)

    @http.route('/livekit/webhook/agent/<int:agent_id>/transcript',
                methods=['POST'], type='http', auth='public', csrf=False)
    def agent_transcript(self, agent_id, **kw):
        agent = self._get_agent_checked(agent_id)
        if not agent:
            return self._json({'error': 'unauthorized'}, status=403)
        payload, error = self._read_ai_payload(MAX_AI_TRANSCRIPT_BYTES)
        if error:
            return error
        rec_id = request.env['connect.call'].with_user(
            request.env.ref('connect.user_connect_webhook')
        ).livekit_apply_agent_transcript(agent, payload)
        return self._json({'status': 'ok', 'recording_id': rec_id})
