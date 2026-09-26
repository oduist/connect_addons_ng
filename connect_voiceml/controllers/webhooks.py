# -*- coding: utf-8 -*-
import logging

from odoo.http import request, Controller, route

from odoo.addons.connect_voiceml.models.webhook import valid_request, normalize_url

logger = logging.getLogger(__name__)


class ConnectVoiceMLController(Controller):

    @staticmethod
    def check_signature():
        settings = request.env['connect.settings'].sudo()
        if not settings.get_param('voiceml_verify_requests'):
            return True
        secret = settings.get_param('api_key')
        url = normalize_url(request.httprequest.url)
        signature = request.httprequest.headers.get('X-Twilio-Signature', '')
        params = (
            request.httprequest.form.to_dict()
            if request.httprequest.method == 'POST'
            else {}
        )
        request_valid = valid_request(url, params, signature, secret)
        if not request_valid:
            if request.httprequest.url.startswith('http:'):
                logger.error('VoiceML requires HTTPS to be setup!')
            else:
                logger.error('VoiceML request is not valid!')
        return request_valid

    def _fail(self):
        return '<Response><Say>Invalid VoiceML request!</Say></Response>'

    @route('/voiceml/webhook/domain', methods=['POST'], type='http', auth='public', csrf=False)
    def domain_webhook(self, **kw):
        if not self.check_signature():
            return self._fail()
        domain = request.env['connect.voiceml.domain'].with_user(request.env.ref("connect.user_connect_webhook"))
        return '{}'.format(domain.route_call(kw))

    @route('/voiceml/webhook/callstatus', methods=['POST'], type='http', auth='public', csrf=False)
    def callstatus_webhook(self, **kw):
        if not self.check_signature():
            return ''
        res = request.env['connect.call'].with_user(request.env.ref("connect.user_connect_webhook")).on_call_status(kw)
        return '{}'.format(res)

    @route('/voiceml/webhook/number', methods=['POST'], type='http', auth='public', csrf=False)
    def number_webhook(self, **kw):
        if not self.check_signature():
            return self._fail()
        res = request.env['connect.voiceml.number'].with_user(request.env.ref("connect.user_connect_webhook")).route_call(kw)
        return '{}'.format(res)

    @route('/voiceml/webhook/outgoing_callerid', methods=['POST'], type='http', auth='public', csrf=False)
    def outgoing_callerid_webhook(self, **kw):
        if not self.check_signature():
            return ''
        outgoing_callerid = request.env['connect.voiceml.outgoing_callerid'].with_user(request.env.ref("connect.user_connect_webhook"))
        return '{}'.format(outgoing_callerid.update_status(kw))

    @route('/voiceml/webhook/callflow/<int:flow_id>/gather', methods=['POST'], type='http', auth='public', csrf=False)
    def gather_webhook(self, flow_id, **kw):
        if not self.check_signature():
            return self._fail()
        callflow = request.env['connect.voiceml.callflow'].with_user(request.env.ref("connect.user_connect_webhook"))
        return '{}'.format(callflow.gather_action(flow_id, kw))

    @route('/voiceml/webhook/vm_recordingstatus', methods=['POST'], type='http', auth='public', csrf=False)
    def vm_recording_status_webhook(self, **kw):
        if not self.check_signature():
            return self._fail()
        call = request.env['connect.call'].with_user(request.env.ref("connect.user_connect_webhook"))
        return '{}'.format(call.on_vm_recording_status(kw))

    @route('/voiceml/webhook/<string:model_name>/call_action/<int:record_id>', methods=['POST'], type='http', auth='public', csrf=False)
    def call_action_edit_webhook(self, model_name, record_id, **kw):
        if not self.check_signature():
            return self._fail()
        model = request.env[model_name].with_user(request.env.ref("connect.user_connect_webhook"))
        res = model.on_call_action(record_id, kw)
        return '{}'.format(res)

    @route('/voiceml/webhook/recordingstatus', methods=['POST'], type='http', auth='public', csrf=False)
    def recording_status_webhook(self, **kw):
        if not self.check_signature():
            return ''
        recording = request.env['connect.recording'].with_user(request.env.ref("connect.user_connect_webhook"))
        return '{}'.format(recording.on_recording_status(kw))

    @route('/voiceml/webhook/callaction', methods=['POST'], type='http', auth='public', csrf=False)
    def call_action_webhook(self, **kw):
        if not self.check_signature():
            return self._fail()
        call = request.env['connect.call'].with_user(request.env.ref("connect.user_connect_webhook"))
        return '{}'.format(call.on_call_action(kw))

    @route('/voiceml/webhook/application/<int:application_id>', methods=['POST'], type='http', auth='public', csrf=False)
    def application_webhook(self, application_id, **kw):
        if not self.check_signature():
            return self._fail()
        application = request.env['connect.voiceml.application'].with_user(request.env.ref("connect.user_connect_webhook"))
        return '{}'.format(application.browse(application_id).render(kw))

    @route('/voiceml/webhook/message', methods=['POST'], type='http', auth='public', csrf=False)
    def message_webhook(self, **kw):
        if not self.check_signature():
            return self._fail()
        message = request.env['connect.message'].with_user(request.env.ref("connect.user_connect_webhook"))
        return '{}'.format(message.receive(kw))

    @route('/voiceml/webhook/message_status', methods=['POST'], type='http', auth='public', csrf=False)
    def message_status_webhook(self, **kw):
        if not self.check_signature():
            return ''
        request.env['connect.message'].with_user(request.env.ref("connect.user_connect_webhook")).receive(kw)
        return 'OK'
