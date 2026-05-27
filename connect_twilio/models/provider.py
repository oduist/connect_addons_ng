"""Twilio provider adapter: implements abstracts on `connect.provider`.

ODU-4 introduced `_originate_call`; ODU-15 adds `_verify_webhook` for
the unified webhook auth surface.
"""
import logging

from twilio.request_validator import RequestValidator

from odoo import models

logger = logging.getLogger(__name__)


class TwilioProvider(models.Model):
    _inherit = 'connect.provider'

    def _originate_call(self, number, res_model=None, res_id=None, user=None, **kwargs):
        if self.code != 'twilio':
            return super()._originate_call(
                number=number, res_model=res_model, res_id=res_id, user=user, **kwargs
            )
        return self.env['connect.provider.twilio.config'].sudo()._originate_call(
            number=number, res_model=res_model, res_id=res_id, user=user, **kwargs
        )

    def _phone_adapter_module(self):
        if self.code != 'twilio':
            return super()._phone_adapter_module()
        return 'connect_twilio/static/src/js/main.js'

    def _active_calls_tray_module(self):
        if self.code != 'twilio':
            return super()._active_calls_tray_module()
        return 'connect_twilio/static/src/services/active_calls/active_calls_main.js'

    def _message_action_modules(self):
        if self.code != 'twilio':
            return super()._message_action_modules()
        return ['connect_twilio/static/src/services/mail/message_actions.js']

    def _verify_webhook(self, request, data=None):
        if self.code != 'twilio':
            return super()._verify_webhook(request, data=data)
        cfg = self.env['connect.provider.twilio.config'].sudo()._get()
        if not cfg.verify_requests:
            return True
        validator = RequestValidator(cfg.auth_token)
        url = request.httprequest.url.replace('http:', 'https:')
        signature = request.httprequest.headers.get('X-Twilio-Signature', '')
        ok = validator.validate(url, data or {}, signature)
        if not ok:
            logger.warning('Twilio webhook signature mismatch on %s', url)
        return ok
