# -*- coding: utf-8 -*-
import json
import logging

from odoo.http import Controller, request, route

from .token_auth import check_infobip_webhook_auth, unauthorized_response

logger = logging.getLogger(__name__)


class ConnectInfobipController(Controller):
    """Infobip webhook endpoints (ADR-036).

    All routes are public POST JSON endpoints authenticated by the shared
    webhook token, executed as the special webhook user, and declared
    readonly=False explicitly — every handler writes ledger records and
    issues REST call-control actions.
    """

    def _parse_event(self):
        try:
            return json.loads(request.httprequest.get_data() or b'{}')
        except ValueError:
            logger.error('Infobip webhook: invalid JSON body.')
            return None

    def _webhook_model(self, model):
        return request.env[model].with_user(
            request.env.ref('connect.user_connect_webhook'))

    def _handle(self, model, method):
        if not check_infobip_webhook_auth():
            return unauthorized_response()
        event = self._parse_event()
        if event is None:
            return request.make_json_response({}, status=400)
        getattr(self._webhook_model(model), method)(event)
        return request.make_json_response({})

    @route('/infobip/webhook/voice/received', methods=['POST'], type='http',
           auth='public', csrf=False, readonly=False)
    def voice_received(self, **kw):
        if not check_infobip_webhook_auth():
            return unauthorized_response()
        event = self._parse_event()
        if event is None:
            return request.make_json_response({}, status=400)
        self._webhook_model('connect.call').on_infobip_voice_event(
            event, 'received')
        return request.make_json_response({})

    @route('/infobip/webhook/voice/event', methods=['POST'], type='http',
           auth='public', csrf=False, readonly=False)
    def voice_event(self, **kw):
        if not check_infobip_webhook_auth():
            return unauthorized_response()
        event = self._parse_event()
        if event is None:
            return request.make_json_response({}, status=400)
        self._webhook_model('connect.call').on_infobip_voice_event(
            event, 'event')
        return request.make_json_response({})

    @route('/infobip/webhook/message', methods=['POST'], type='http',
           auth='public', csrf=False, readonly=False)
    def message(self, **kw):
        return self._handle('connect.message', 'infobip_receive')

    @route('/infobip/webhook/whatsapp', methods=['POST'], type='http',
           auth='public', csrf=False, readonly=False)
    def whatsapp(self, **kw):
        return self._handle('connect.message', 'infobip_receive_whatsapp')

    @route('/infobip/webhook/message_status', methods=['POST'], type='http',
           auth='public', csrf=False, readonly=False)
    def message_status(self, **kw):
        return self._handle(
            'connect.message', 'infobip_process_delivery_report')
