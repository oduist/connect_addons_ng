# -*- coding: utf-8 -*-
import json
import logging

from odoo.http import request, Controller, route
from telnyx.lib.webhook_verification import (
    verify_webhook_signature,
    WebhookVerificationError,
)

logger = logging.getLogger(__name__)


class ConnectTelnyxController(Controller):

    @staticmethod
    def check_signature():
        """Validate the Ed25519 signature over the raw request body
        (telnyx-signature-ed25519 / telnyx-timestamp headers)."""
        settings = request.env['connect.settings'].sudo()
        if not settings.get_param('telnyx_verify_requests'):
            return True
        public_key = settings.get_param('telnyx_public_key')
        if not public_key:
            logger.error('Telnyx public key is not configured!')
            return False
        try:
            verify_webhook_signature(
                request.httprequest.get_data(),
                dict(request.httprequest.headers),
                public_key,
            )
            return True
        except WebhookVerificationError as e:
            logger.error('Telnyx request is not valid: %s', e)
            return False

    @route('/telnyx/webhook/domain', methods=['POST'], type='http', auth='public', csrf=False)
    def domain_webhook(self, **kw):
        if not self.check_signature():
            return '<Response><Say>Invalid Telnyx request!</Say></Response>'
        domain = request.env['connect.telnyx.domain'].with_user(request.env.ref("connect.user_connect_webhook"))
        res = domain.route_call(kw)
        return f'{res}'

    @route('/telnyx/webhook/callstatus', methods=['POST'], type='http', auth='public', csrf=False)
    def callstatus_webhook(self, **kw):
        if not self.check_signature():
            return False
        res = request.env['connect.call'].with_user(request.env.ref("connect.user_connect_webhook")).on_telnyx_call_status(kw)
        return f'{res}'

    @route('/telnyx/webhook/number', methods=['POST'], type='http', auth='public', csrf=False)
    def number_webhook(self, **kw):
        if not self.check_signature():
            return '<Response><Say>Invalid Telnyx request!</Say></Response>'
        res = request.env['connect.telnyx.number'].with_user(request.env.ref("connect.user_connect_webhook")).route_call(kw)
        return f'{res}'

    @route('/telnyx/webhook/callflow/<int:flow_id>/gather', methods=['POST'], type='http', auth='public', csrf=False)
    def gather_webhook(self, flow_id, **kw):
        if not self.check_signature():
            return '<Response><Say>Invalid Telnyx request!</Say></Response>'
        callflow = request.env['connect.telnyx.callflow'].with_user(request.env.ref("connect.user_connect_webhook"))
        res = callflow.gather_action(flow_id, kw)
        return f'{res}'

    @route('/telnyx/webhook/vm_recordingstatus', methods=['POST'], type='http', auth='public', csrf=False)
    def vm_recording_status_webhook(self, **kw):
        if not self.check_signature():
            return '<Response><Say>Invalid Telnyx request!</Say></Response>'
        call = request.env['connect.call'].with_user(request.env.ref("connect.user_connect_webhook"))
        res = call.on_telnyx_vm_recording_status(kw)
        return f'{res}'

    @route('/telnyx/webhook/<string:model_name>/call_action/<int:record_id>', methods=['POST'], type='http', auth='public', csrf=False)
    def call_action_edit_webhook(self, model_name, record_id, **kw):
        if not self.check_signature():
            return '<Response><Say>Invalid Telnyx request!</Say></Response>'
        model = request.env[model_name].with_user(request.env.ref("connect.user_connect_webhook"))
        # connect.user is a shared ledger model, so its Telnyx call-action
        # method carries the telnyx_ prefix (connect_twilio owns the
        # unprefixed name).
        if model_name == 'connect.user':
            res = model.telnyx_on_call_action(record_id, kw)
        else:
            res = model.on_call_action(record_id, kw)
        return f'{res}'

    @route('/telnyx/webhook/recordingstatus', methods=['POST'], type='http', auth='public', csrf=False)
    def recording_status_webhook(self, **kw):
        if not self.check_signature():
            return False
        recording = request.env['connect.recording'].with_user(request.env.ref("connect.user_connect_webhook"))
        res = recording.on_telnyx_recording_status(kw)
        return f'{res}'

    @route('/telnyx/webhook/callaction', methods=['POST'], type='http', auth='public', csrf=False)
    def call_action_webhook(self, **kw):
        if not self.check_signature():
            return '<Response><Say>Invalid Telnyx request!</Say></Response>'
        call = request.env['connect.call'].with_user(request.env.ref("connect.user_connect_webhook"))
        res = call.telnyx_on_call_action(kw)
        return f'{res}'

    @route('/telnyx/webhook/texml/<int:texml_id>', methods=['POST'], type='http', auth='public', csrf=False)
    def texml_webhook(self, texml_id, **kw):
        if not self.check_signature():
            return '<Response><Say>Invalid Telnyx request!</Say></Response>'
        texml = request.env['connect.telnyx.texml'].with_user(request.env.ref("connect.user_connect_webhook"))
        res = texml.browse(texml_id).render(kw)
        return f'{res}'

    @route('/telnyx/webhook/message', methods=['POST'], type='http', auth='public', csrf=False)
    def message_webhook(self, **kw):
        # Telnyx messaging webhooks are v2 JSON envelopes, not form data.
        if not self.check_signature():
            return 'Invalid Telnyx request!'
        try:
            event = json.loads(request.httprequest.get_data() or b'{}')
        except ValueError:
            logger.error('Cannot parse Telnyx message webhook body!')
            return ''
        message = request.env['connect.message'].with_user(request.env.ref("connect.user_connect_webhook"))
        res = message.telnyx_receive(event)
        return f'{res}'
