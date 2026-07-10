import json
import logging
import secrets

from odoo import http
from odoo.http import Response, request

logger = logging.getLogger(__name__)


class PipecatController(http.Controller):

    @staticmethod
    def _json(payload, status=200, headers=None):
        return Response(
            json.dumps(payload, default=str), status=status,
            content_type='application/json', headers=headers,
        )

    @classmethod
    def _unauthorized(cls):
        return cls._json(
            {'error': 'unauthorized'}, status=401,
            headers=[('WWW-Authenticate', 'Bearer')],
        )

    @staticmethod
    def _check_token():
        expected = request.env['connect.settings'].sudo().get_param(
            'pipecat_service_token',
        ) or ''
        auth = request.httprequest.headers.get('Authorization', '')
        if not expected or not auth.lower().startswith('bearer '):
            return False
        return secrets.compare_digest(auth[7:].strip(), expected)

    @staticmethod
    def _payload():
        raw = request.httprequest.get_data(as_text=True) or ''
        return json.loads(raw) if raw else {}

    @staticmethod
    def _webhook_env(model):
        return request.env[model].with_user(
            request.env.ref('connect.user_connect_webhook').id,
        )

    @http.route(
        '/pipecat/agent/<int:agent_id>', type='http', auth='none',
        methods=['GET'], csrf=False,
    )
    def agent(self, agent_id, **_kwargs):
        if not self._check_token():
            return self._unauthorized()
        agent = self._webhook_env('connect.pipecat.agent').browse(agent_id).exists()
        if not agent or not agent.active:
            return self._json({'error': 'not_found'}, status=404)
        settings = request.env['connect.settings'].sudo()
        api_keys = {
            'openai': settings.get_param('openai_api_key') or '',
            'deepgram': settings.get_param('deepgram_api_key') or '',
            'elevenlabs': settings.get_param('elevenlabs_api_key') or '',
            'anthropic': settings.get_param('anthropic_api_key') or '',
        }
        return self._json({
            'id': agent.id,
            'name': agent.name,
            'system_prompt': agent.system_prompt,
            'greeting': agent.greeting or '',
            'language': agent.language,
            'stt': {
                'provider': agent.stt_provider,
                'model': agent.stt_model,
                'api_key': api_keys.get(agent.stt_provider, ''),
            },
            'llm': {
                'provider': agent.llm_provider,
                'model': agent.llm_model,
                'api_key': api_keys.get(agent.llm_provider, ''),
            },
            'tts': {
                'provider': agent.tts_provider,
                'model': agent.tts_model,
                'voice': agent.tts_voice,
                'api_key': api_keys.get(agent.tts_provider, ''),
            },
            'transfer': {
                'enabled': bool(agent.transfer_exten),
                'prompt': agent.transfer_prompt or '',
            },
            'max_duration': agent.max_duration,
        })

    @http.route(
        '/pipecat/call-result', type='http', auth='none', methods=['POST'],
        csrf=False, readonly=False,
    )
    def call_result(self, **_kwargs):
        if not self._check_token():
            return self._unauthorized()
        try:
            payload = self._payload()
        except ValueError:
            return self._json({'error': 'bad_json'}, status=400)
        call_uuid = payload.get('call_uuid')
        if not call_uuid:
            return self._json({'error': 'call_uuid_required'}, status=400)
        channel = self._webhook_env('connect.channel').search(
            [('sid', '=', call_uuid)], limit=1,
        )
        if not channel:
            return self._json({'error': 'call_not_found'}, status=404)
        summary = payload.get('summary') or ''
        transcript = payload.get('transcript') or ''
        if channel.call:
            channel.call.write({'summary': summary})
        recording = self._webhook_env('connect.recording').search([
            '|', ('call_sid', '=', call_uuid), ('channel', '=', channel.id),
        ], limit=1)
        if recording:
            recording.with_context(tracking_disable=True).write({
                'transcript': transcript,
                'summary': summary,
                'transcription_pending': False,
                'transcription_error': False,
            })
        return self._json({
            'ok': True,
            'call_id': channel.call.id if channel.call else False,
            'recording_id': recording.id if recording else False,
        })

    @http.route(
        '/pipecat/hangup', type='http', auth='none', methods=['POST'],
        csrf=False, readonly=False,
    )
    def hangup(self, **_kwargs):
        if not self._check_token():
            return self._unauthorized()
        try:
            call_uuid = self._payload().get('call_uuid')
        except ValueError:
            return self._json({'error': 'bad_json'}, status=400)
        if not call_uuid:
            return self._json({'error': 'call_uuid_required'}, status=400)
        result = request.env['connect.settings'].sudo().freeswitch_api(
            'uuid_kill', call_uuid,
        )
        return self._json({'ok': result is not False})

    @http.route(
        '/pipecat/transfer', type='http', auth='none', methods=['POST'],
        csrf=False, readonly=False,
    )
    def transfer(self, **_kwargs):
        if not self._check_token():
            return self._unauthorized()
        try:
            payload = self._payload()
        except ValueError:
            return self._json({'error': 'bad_json'}, status=400)
        call_uuid = payload.get('call_uuid')
        agent_id = payload.get('agent_id')
        if not call_uuid or not agent_id:
            return self._json({'error': 'call_uuid_and_agent_id_required'}, status=400)
        try:
            agent_id = int(agent_id)
        except (TypeError, ValueError):
            return self._json({'error': 'invalid_agent_id'}, status=400)
        agent = self._webhook_env('connect.pipecat.agent').browse(
            agent_id,
        ).exists()
        if not agent or not agent.transfer_exten:
            return self._json({'error': 'transfer_not_configured'}, status=409)
        settings = request.env['connect.settings'].sudo()
        settings.freeswitch_api('uuid_audio_fork', '{} stop'.format(call_uuid))
        result = settings.freeswitch_api(
            'uuid_transfer', '{} {}'.format(call_uuid, agent.transfer_exten.number),
        )
        return self._json({'ok': result is not False})
