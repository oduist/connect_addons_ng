# -*- coding: utf-8 -*-
"""Single webhook endpoint for all Bird platform events.

Bird follows the Standard Webhooks specification: every delivery is
wrapped in a ``{"type", "timestamp", "data"}`` envelope and signed with
HMAC-SHA256 over ``"{webhook-id}.{webhook-timestamp}.{raw body}"``
(headers ``webhook-id`` / ``webhook-timestamp`` / ``webhook-signature``
with ``v1,<base64>`` values; the key is the base64 payload of the
``whsec_...`` secret issued once when the endpoint is registered).

Like the other providers, event processing dispatches under the core
webhook user (``connect.user_connect_webhook``). Handlers are idempotent
and the endpoint answers 200 even on processing errors: Bird retries
failed deliveries, and replaying a poison-pill payload would only spam
the log. Signature failures answer 401 so Bird keeps retrying while a
secret misconfiguration is being fixed.
"""
import base64
import hashlib
import hmac
import json
import logging
import time

from odoo import http
from odoo.http import Response, request

logger = logging.getLogger(__name__)


class BirdWebhooksController(http.Controller):

    @staticmethod
    def _verify_signature(raw):
        settings = request.env['connect.settings'].sudo()
        if not settings.get_param('bird_verify_requests'):
            return True
        secret = settings.get_param('bird_webhook_signing_key') or ''
        headers = request.httprequest.headers
        webhook_id = headers.get('webhook-id', '')
        timestamp = headers.get('webhook-timestamp', '')
        signature_header = headers.get('webhook-signature', '')
        if not (secret and webhook_id and timestamp and timestamp.isdigit()
                and signature_header):
            logger.error('Bird webhook without signature headers or secret.')
            return False
        tolerance = int(settings.get_param('bird_signature_tolerance') or 300)
        if abs(time.time() - int(timestamp)) > tolerance:
            logger.error('Bird webhook timestamp outside tolerance.')
            return False
        try:
            key = base64.b64decode(
                secret.split('_', 1)[1] if secret.startswith('whsec_')
                else secret)
        except Exception:
            logger.error('Bird webhook signing secret is malformed.')
            return False
        signed = '{}.{}.'.format(webhook_id, timestamp).encode() + raw
        expected = base64.b64encode(
            hmac.new(key, signed, hashlib.sha256).digest()).decode()
        # The header may carry several space-separated versioned
        # signatures (e.g. during secret rotation).
        for candidate in signature_header.split(' '):
            version, _, value = candidate.partition(',')
            if version == 'v1' and value \
                    and hmac.compare_digest(expected, value):
                return True
        logger.error('Bird webhook signature mismatch.')
        return False

    @http.route('/bird/webhook', type='http', auth='public',
                methods=['POST'], csrf=False, readonly=False)
    def bird_webhook(self, **kw):
        raw = request.httprequest.get_data()
        if not self._verify_signature(raw):
            return Response('invalid signature', status=401)
        try:
            envelope = json.loads(raw)
        except ValueError:
            return Response('bad json', status=400)
        event_type = envelope.get('type') or ''
        data = envelope.get('data') or {}
        webhook_user = request.env.ref('connect.user_connect_webhook')
        env = request.env(user=webhook_user.id)
        try:
            product = event_type.split('.')[0]
            action = event_type.split('.')[-1]
            if product in ('sms', 'whatsapp'):
                if action in ('received', 'inbound'):
                    env['connect.message'].receive_bird(data, event_type)
                else:
                    env['connect.message'].update_bird_status(
                        data, event_type)
            elif product == 'voice':
                env['connect.call'].on_bird_call_event(data, event_type)
            else:
                logger.info('Unhandled Bird webhook event: %s', event_type)
        except Exception:
            logger.exception('Error processing Bird webhook event %s:',
                             event_type)
        return Response(
            json.dumps({'ok': True}), status=200,
            content_type='application/json')
