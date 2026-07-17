# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
import logging

import jwt as pyjwt

from odoo.http import Controller, Response, request, route

logger = logging.getLogger(__name__)

# Models allowed in the generic call_action route.
CALL_ACTION_MODELS = ('connect.user', 'connect.callflow')


class ConnectVonageController(Controller):
    """Vonage webhook endpoints (ADR-036).

    All routes are public POST JSON endpoints authenticated by the signed
    callback JWT (Authorization: Bearer, HS256 with the account signature
    secret + payload_hash check), executed as the special webhook user,
    and declared readonly=False explicitly — handlers write channel/call/
    message/recording records.
    """

    @staticmethod
    def check_signature():
        settings = request.env['connect.settings'].sudo()
        if not settings.get_param('vonage_verify_requests'):
            return True
        signature_secret = settings.get_param('vonage_signature_secret')
        if not signature_secret:
            logger.error(
                'Vonage signature secret is not set, rejecting webhook!')
            return False
        auth_header = request.httprequest.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            logger.error('Vonage webhook without a bearer token!')
            return False
        token = auth_header.split(' ', 1)[1].strip()
        try:
            claims = pyjwt.decode(
                token, signature_secret, algorithms=['HS256'])
        except Exception as e:
            logger.error('Vonage webhook JWT validation failed: %s', e)
            return False
        payload_hash = claims.get('payload_hash')
        if payload_hash:
            body = request.httprequest.get_data() or b''
            digest = hashlib.sha256(body).hexdigest()
            if not hmac.compare_digest(digest, payload_hash):
                logger.error('Vonage webhook payload hash mismatch!')
                return False
        return True

    @staticmethod
    def _json_params():
        try:
            return json.loads(request.httprequest.get_data() or b'{}')
        except ValueError:
            logger.error('Vonage webhook: invalid JSON body.')
            return {}

    @staticmethod
    def _webhook_model(model):
        return request.env[model].with_user(
            request.env.ref('connect.user_connect_webhook'))

    @staticmethod
    def _ncco_response(ncco):
        return Response(
            json.dumps(ncco if ncco is not None else []),
            content_type='application/json', status=200)

    @staticmethod
    def _unauthorized():
        return Response('Unauthorized', status=401)

    @route('/vonage/webhook/answer', methods=['GET', 'POST'], type='http',
           auth='public', csrf=False, readonly=False)
    def answer(self, **kw):
        if not self.check_signature():
            return self._unauthorized()
        params = self._json_params() or dict(kw)
        if params.get('from_user'):
            # Outbound call placed from the Client SDK web phone.
            ncco = self._webhook_model('connect.user').on_client_call(params)
        else:
            ncco = self._webhook_model('connect.number').route_call(params)
        return self._ncco_response(ncco)

    @route('/vonage/webhook/event', methods=['POST'], type='http',
           auth='public', csrf=False, readonly=False)
    def event(self, **kw):
        if not self.check_signature():
            return self._unauthorized()
        params = self._json_params()
        self._webhook_model('connect.call').on_voice_event(params)
        return 'OK'

    @route('/vonage/webhook/recording', methods=['POST'], type='http',
           auth='public', csrf=False, readonly=False)
    def recording(self, **kw):
        if not self.check_signature():
            return self._unauthorized()
        params = self._json_params()
        self._webhook_model('connect.recording').on_recording_event(params)
        return 'OK'

    @route('/vonage/webhook/vm_recording', methods=['POST'], type='http',
           auth='public', csrf=False, readonly=False)
    def vm_recording(self, **kw):
        if not self.check_signature():
            return self._unauthorized()
        params = self._json_params()
        self._webhook_model('connect.recording').on_vm_recording_event(params)
        return 'OK'

    @route('/vonage/webhook/ncco/<int:ncco_id>', methods=['GET', 'POST'],
           type='http', auth='public', csrf=False, readonly=False)
    def ncco(self, ncco_id, **kw):
        if not self.check_signature():
            return self._unauthorized()
        params = self._json_params() or dict(kw)
        ncco = self._webhook_model('connect.ncco').browse(ncco_id).render(
            params)
        return self._ncco_response(ncco)

    @route('/vonage/webhook/<string:model_name>/call_action/<int:record_id>',
           methods=['POST'], type='http', auth='public', csrf=False,
           readonly=False)
    def call_action(self, model_name, record_id, **kw):
        if not self.check_signature():
            return self._unauthorized()
        if model_name not in CALL_ACTION_MODELS:
            logger.error('call_action for unexpected model %s', model_name)
            return Response('Not found', status=404)
        params = self._json_params()
        res = self._webhook_model(model_name).on_call_action(
            record_id, params)
        if res is None:
            # An empty body tells Vonage to continue the current NCCO.
            return Response('', status=204)
        return self._ncco_response(res)

    @route('/vonage/webhook/callflow/<int:flow_id>/input', methods=['POST'],
           type='http', auth='public', csrf=False, readonly=False)
    def callflow_input(self, flow_id, **kw):
        if not self.check_signature():
            return self._unauthorized()
        params = self._json_params()
        ncco = self._webhook_model('connect.callflow').gather_action(
            flow_id, params)
        return self._ncco_response(ncco)

    @route('/vonage/webhook/message', methods=['POST'], type='http',
           auth='public', csrf=False, readonly=False)
    def message(self, **kw):
        if not self.check_signature():
            return self._unauthorized()
        params = self._json_params()
        self._webhook_model('connect.message').receive(params)
        return 'OK'

    @route('/vonage/webhook/message_status', methods=['POST'], type='http',
           auth='public', csrf=False, readonly=False)
    def message_status(self, **kw):
        if not self.check_signature():
            return self._unauthorized()
        params = self._json_params()
        self._webhook_model('connect.message').update_message_status(params)
        return 'OK'

    @route('/vonage/webhook/rtc', methods=['POST'], type='http',
           auth='public', csrf=False, readonly=False)
    def rtc(self, **kw):
        if not self.check_signature():
            return self._unauthorized()
        params = self._json_params()
        logger.debug('Vonage RTC event: %s', json.dumps(params))
        return 'OK'
