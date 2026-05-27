"""ElevenLabs provider adapter — webhook auth via header token
(ODU-15 / ADR-023 Phase 7)."""
import hmac
import hashlib
import logging
import time

from odoo import models

logger = logging.getLogger(__name__)


class ElevenLabsProvider(models.Model):
    _inherit = 'connect.provider'

    def _verify_webhook(self, request, data=None):
        """EL webhooks come in two flavours:
        - Agent / tool calls: `x-elevenlabs-agent-token` header equals
          `agent_token` on the provider config (the secret the agent
          uses on outbound tool calls).
        - Post-call webhook: HMAC-SHA256 of `<timestamp>.<payload>`
          signed with the post-call webhook secret, transmitted in
          `elevenlabs-signature` header.

        `data='post_call'` selects the HMAC path; default selects the
        agent-token path.
        """
        if self.code != 'elevenlabs':
            return super()._verify_webhook(request, data=data)
        cfg = self.env['connect.provider.elevenlabs.config'].sudo()._get()
        if data == 'post_call':
            return self._verify_post_call(request, cfg)
        return self._verify_agent_token(request, cfg)

    @staticmethod
    def _verify_agent_token(request, cfg):
        token = request.httprequest.headers.get('x-elevenlabs-agent-token')
        if not token:
            logger.warning('EL agent-token check: header missing')
            return False
        expected = cfg.agent_token
        if not expected:
            logger.warning('EL agent-token check: provider not configured')
            return False
        if token != expected:
            logger.warning('EL agent-token mismatch (received %s…)', token[:8])
            return False
        return True

    @staticmethod
    def _verify_post_call(request, cfg):
        payload = request.httprequest.get_data(as_text=True)
        header = request.httprequest.headers.get('elevenlabs-signature')
        if not header:
            logger.warning('EL post-call: signature header missing')
            return False
        try:
            timestamp_part, sig_part = header.split(',', 1)
            timestamp = timestamp_part[2:]
            tolerance = int(time.time()) - 30 * 60
            if int(timestamp) < tolerance:
                logger.info('EL post-call: stale timestamp')
                return False
        except (ValueError, IndexError):
            logger.warning('EL post-call: malformed signature header')
            return False
        full_payload_to_sign = f'{timestamp}.{payload}'
        secret = cfg.post_call_webhook_secret or ''
        if not secret:
            return False
        mac = hmac.new(secret.encode('utf-8'),
                       full_payload_to_sign.encode('utf-8'),
                       hashlib.sha256)
        expected_sig = 'v0=' + mac.hexdigest()
        return hmac.compare_digest(expected_sig, sig_part.strip())
