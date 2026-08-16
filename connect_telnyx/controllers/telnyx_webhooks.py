# -*- coding: utf-8 -*-
import json
import logging
import hmac

from odoo.http import request, Controller, route
from telnyx.lib.webhook_verification import (
    verify_webhook_signature,
    WebhookVerificationError,
)

logger = logging.getLogger(__name__)

MAX_AI_WEBHOOK_BYTES = 64 * 1024


class ConnectTelnyxController(Controller):

    @staticmethod
    def _texml_response(content):
        return request.env[
            'connect.settings'].sudo().telnyx_apply_system_voice(content)

    @staticmethod
    def signed_body():
        """Return the original bytes captured before Odoo parses the form."""
        return request.httprequest.environ.get('connect_telnyx.raw_body')

    @classmethod
    def check_signature(cls):
        """Validate the Ed25519 signature over the raw request body
        (telnyx-signature-ed25519 / telnyx-timestamp headers)."""
        settings = request.env['connect.settings'].sudo()
        if not settings.get_param('telnyx_verify_requests'):
            return True
        public_key = settings.get_param('telnyx_public_key')
        if not public_key:
            logger.error('Telnyx public key is not configured!')
            return False
        body = cls.signed_body()
        if body is None:
            logger.error(
                'Raw body was not captured for Telnyx request to %s',
                request.httprequest.path)
            return False
        headers = dict(request.httprequest.headers)
        try:
            verify_webhook_signature(body, headers, public_key)
            return True
        except WebhookVerificationError as error:
            logger.error(
                'Telnyx request to %s is not valid: %s '
                '(content type %s, %s body bytes)',
                request.httprequest.path, error,
                request.httprequest.content_type, len(body))
            return False

    @route('/telnyx/webhook/domain', methods=['POST'], type='http', auth='public', csrf=False, readonly=False)
    def domain_webhook(self, **kw):
        if not self.check_signature():
            return self._texml_response(
                '<Response><Say>Invalid Telnyx request!</Say></Response>')
        domain = request.env['connect.telnyx.domain'].with_user(request.env.ref("connect.user_connect_webhook"))
        res = domain.route_call(kw)
        return self._texml_response(res)

    @route('/telnyx/webhook/callstatus', methods=['POST'], type='http', auth='public', csrf=False, readonly=False)
    def callstatus_webhook(self, **kw):
        if not self.check_signature():
            return ''
        res = request.env['connect.call'].with_user(request.env.ref("connect.user_connect_webhook")).on_telnyx_call_status(kw)
        return f'{res}'

    @route('/telnyx/webhook/number', methods=['POST'], type='http', auth='public', csrf=False, readonly=False)
    def number_webhook(self, **kw):
        if not self.check_signature():
            return self._texml_response(
                '<Response><Say>Invalid Telnyx request!</Say></Response>')
        res = request.env['connect.telnyx.number'].with_user(request.env.ref("connect.user_connect_webhook")).route_call(kw)
        return self._texml_response(res)

    @route('/telnyx/webhook/callflow/<int:flow_id>/gather', methods=['POST'], type='http', auth='public', csrf=False, readonly=False)
    def gather_webhook(self, flow_id, **kw):
        if not self.check_signature():
            return self._texml_response(
                '<Response><Say>Invalid Telnyx request!</Say></Response>')
        callflow = request.env['connect.telnyx.callflow'].with_user(request.env.ref("connect.user_connect_webhook"))
        res = callflow.gather_action(flow_id, kw)
        return self._texml_response(res)

    @route('/telnyx/webhook/vm_recordingstatus', methods=['POST'], type='http', auth='public', csrf=False, readonly=False)
    def vm_recording_status_webhook(self, **kw):
        if not self.check_signature():
            return self._texml_response(
                '<Response><Say>Invalid Telnyx request!</Say></Response>')
        call = request.env['connect.call'].with_user(request.env.ref("connect.user_connect_webhook"))
        res = call.on_telnyx_vm_recording_status(kw)
        return self._texml_response(res)

    @route('/telnyx/webhook/<string:model_name>/call_action/<int:record_id>', methods=['POST'], type='http', auth='public', csrf=False, readonly=False)
    def call_action_edit_webhook(self, model_name, record_id, **kw):
        if not self.check_signature():
            return '<Response><Hangup/></Response>'
        model = request.env[model_name].with_user(request.env.ref("connect.user_connect_webhook"))
        # connect.user is a shared ledger model, so its Telnyx call-action
        # method carries the telnyx_ prefix (connect_twilio owns the
        # unprefixed name).
        if model_name == 'connect.user':
            res = model.telnyx_on_call_action(record_id, kw)
        else:
            res = model.on_call_action(record_id, kw)
        return self._texml_response(res)

    @route('/telnyx/webhook/recordingstatus', methods=['POST'], type='http', auth='public', csrf=False, readonly=False)
    def recording_status_webhook(self, **kw):
        if not self.check_signature():
            return ''
        recording = request.env['connect.recording'].with_user(request.env.ref("connect.user_connect_webhook"))
        res = recording.on_telnyx_recording_status(kw)
        return f'{res}'

    @route('/telnyx/webhook/callaction', methods=['POST'], type='http', auth='public', csrf=False, readonly=False)
    def call_action_webhook(self, **kw):
        if not self.check_signature():
            return '<Response><Hangup/></Response>'
        call = request.env['connect.call'].with_user(request.env.ref("connect.user_connect_webhook"))
        res = call.telnyx_on_call_action(kw)
        return self._texml_response(res)

    @route('/telnyx/webhook/texml/<int:texml_id>', methods=['POST'], type='http', auth='public', csrf=False, readonly=False)
    def texml_webhook(self, texml_id, **kw):
        if not self.check_signature():
            return self._texml_response(
                '<Response><Say>Invalid Telnyx request!</Say></Response>')
        texml = request.env['connect.telnyx.texml'].with_user(request.env.ref("connect.user_connect_webhook"))
        res = texml.browse(texml_id).render(kw)
        return self._texml_response(res)

    @route('/telnyx/webhook/message', methods=['POST'], type='http', auth='public', csrf=False, readonly=False)
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

    @staticmethod
    def _ai_json_body():
        raw = request.httprequest.get_data() or b'{}'
        if len(raw) > MAX_AI_WEBHOOK_BYTES:
            return None
        try:
            value = json.loads(raw)
        except (TypeError, ValueError):
            return None
        return value if isinstance(value, dict) else None

    @route(
        '/telnyx/webhook/assistant/<int:assistant_id>/variables',
        methods=['POST'], type='http', auth='public', csrf=False, readonly=False,
    )
    def assistant_variables_webhook(self, assistant_id, **kw):
        if not self.check_signature():
            return request.make_json_response(
                {'error': 'invalid_signature'}, status=403)
        event = self._ai_json_body()
        if event is None:
            return request.make_json_response(
                {'error': 'invalid_json'}, status=400)
        assistant = request.env[
            'connect.telnyx.ai_assistant'
        ].with_user(request.env.ref('connect.user_connect_webhook')).browse(
            assistant_id)
        if not assistant.exists():
            return request.make_json_response(
                {'error': 'assistant_not_found'}, status=404)
        payload = (event.get('data') or {}).get('payload') or event.get(
            'payload') or {}
        if payload.get('assistant_id') not in (None, assistant.sid):
            return request.make_json_response(
                {'error': 'assistant_mismatch'}, status=403)
        call = request.env['connect.call'].with_user(
            request.env.ref('connect.user_connect_webhook')
        ).telnyx_link_ai_conversation(payload)
        phone = payload.get('telnyx_end_user_target')
        partner = request.env['res.partner'].sudo().get_partner_by_number(
            phone) if phone else request.env['res.partner']
        if call and partner and not call.partner:
            call.sudo().partner = partner
        result = {
            'dynamic_variables': assistant._partner_values(partner),
            'conversation': {
                'metadata': {
                    'odoo_assistant_id': str(assistant.id),
                    'odoo_partner_id': str(partner.id) if partner else '',
                }
            },
        }
        if assistant.memory_enabled and phone:
            result['memory'] = {
                'conversation_query': (
                    'metadata->telnyx_end_user_target=eq.{}&limit=5'
                    '&order=last_message_at.desc'.format(phone)
                )
            }
        return request.make_json_response(result)

    @route(
        '/telnyx/webhook/assistant/<int:assistant_id>/tool/<string:tool_name>',
        methods=['POST'], type='http', auth='public', csrf=False, readonly=False,
    )
    def assistant_tool_webhook(self, assistant_id, tool_name, **kw):
        assistant = request.env['connect.telnyx.ai_assistant'].sudo().browse(
            assistant_id)
        supplied = request.httprequest.headers.get(
            'X-Odoo-Telnyx-Token', '')
        expected = assistant.tool_token or '' if assistant.exists() else ''
        if not expected or not hmac.compare_digest(supplied, expected):
            return request.make_json_response(
                {'error': 'unauthorized'}, status=403)
        payload = self._ai_json_body()
        if payload is None:
            return request.make_json_response(
                {'error': 'invalid_json'}, status=400)
        try:
            result = assistant.execute_tool(
                tool_name, payload,
                call_control_id=request.httprequest.headers.get(
                    'x-telnyx-call-control-id'),
            )
        except Exception as exc:
            logger.warning('Telnyx AI tool %s failed: %s', tool_name, exc)
            return request.make_json_response(
                {'ok': False, 'error': str(exc)}, status=400)
        return request.make_json_response(result)

    @route(
        '/telnyx/webhook/assistant/insights',
        methods=['POST'], type='http', auth='public', csrf=False, readonly=False,
    )
    def assistant_insights_webhook(self, **kw):
        if not self.check_signature():
            return request.make_json_response(
                {'error': 'invalid_signature'}, status=403)
        payload = self._ai_json_body()
        if payload is None:
            return request.make_json_response(
                {'error': 'invalid_json'}, status=400)
        request.env['connect.call'].with_user(
            request.env.ref('connect.user_connect_webhook')
        ).telnyx_apply_ai_insights(payload)
        return request.make_json_response({'ok': True})
