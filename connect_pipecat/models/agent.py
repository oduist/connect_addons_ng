import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PipecatAgent(models.Model):
    _name = 'connect.pipecat.agent'
    _description = 'Pipecat AI Agent'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    system_prompt = fields.Text(required=True)
    greeting = fields.Text()
    language = fields.Selection(
        selection=lambda self: self.env['connect.freeswitch.callflow']._get_language_selection(),
        default='en-US',
        required=True,
    )
    stt_provider = fields.Selection(
        [('openai', 'OpenAI'), ('deepgram', 'Deepgram')],
        default='deepgram', required=True,
    )
    stt_model = fields.Char(default='nova-3-general', required=True)
    llm_provider = fields.Selection(
        [('openai', 'OpenAI'), ('anthropic', 'Anthropic')],
        default='openai', required=True,
    )
    llm_model = fields.Char(default='gpt-4.1-mini', required=True)
    tts_provider = fields.Selection(
        [('openai', 'OpenAI'), ('elevenlabs', 'ElevenLabs'),
         ('deepgram', 'Deepgram')],
        default='openai', required=True,
    )
    tts_model = fields.Char(default='gpt-4o-mini-tts', required=True)
    tts_voice = fields.Char(default='alloy', required=True)
    transfer_exten = fields.Many2one(
        'connect.freeswitch.exten', ondelete='set null',
        string='Human Transfer Extension',
    )
    transfer_prompt = fields.Text(
        default='Transfer the caller when they explicitly ask for a human.',
    )
    max_duration = fields.Integer(default=1800, required=True)
    record_calls = fields.Boolean(default=True)
    exten = fields.Many2one(
        'connect.freeswitch.exten', ondelete='set null', readonly=True, copy=False,
    )
    exten_number = fields.Char(related='exten.number', store=True)

    @api.constrains('max_duration')
    def _check_max_duration(self):
        for record in self:
            if record.max_duration <= 0:
                raise ValidationError('Maximum duration must be positive.')

    def create_extension(self):
        self.ensure_one()
        return self.env['connect.freeswitch.exten'].create_extension(
            self, 'connect.pipecat.agent',
        )

    def generate_dialplan(self, params, exten=None):
        self.ensure_one()
        settings = self.env['connect.settings'].sudo()
        ws_url = settings.get_pipecat_ws_url()
        service_token = settings.get_param('pipecat_service_token') or ''
        number = exten.number if exten else self.exten_number or str(self.id)
        recording_url = settings.get_recording_webhook_url()
        return self.env['connect.freeswitch.template'].render(
            'dialplan_pipecat_agent', {
                'agent': self,
                'number': re.escape(number),
                'ws_url': ws_url.rstrip('/'),
                'service_token': service_token,
                'record_calls': self.record_calls,
                'recording_url': recording_url.rstrip('/'),
            },
        )
