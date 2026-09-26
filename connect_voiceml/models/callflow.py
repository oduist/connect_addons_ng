# -*- coding: utf-8 -*-
import logging
from urllib.parse import urljoin

from odoo import fields, models, api

from odoo.addons.connect.models.settings import debug
from .twiml_builder import TwiMLResponse

logger = logging.getLogger(__name__)


class CallFlow(models.Model):
    _name = 'connect.voiceml.callflow'
    _description = 'VoiceML Call Flow'
    _order = 'name asc'

    name = fields.Char(required=True)
    exten = fields.Many2one('connect.voiceml.exten', ondelete='set null', readonly=True)
    exten_number = fields.Char(related='exten.number', store=True)
    language = fields.Selection(
        selection=lambda self: self._get_language_selection(),
        default='en-US', required=True, string='Language')
    voice = fields.Char(required=True, default='Woman')
    gather_input = fields.Boolean()
    gather_input_type = fields.Selection(string='Input Type', selection=[
        ('dtmf', 'DTMF'),
        ('speech', 'Speech'),
        ('dtmf speech', 'DTMF + speech'),
    ], required=True, default='dtmf')
    gather_timeout = fields.Integer(string='Timeout', default=5)
    gather_hints = fields.Char('Hints')
    prompt_message = fields.Text('Prompt Message',
        default='Welcome to our company! Please enter the extension number of person '
                'you wish to dial or wait 5 seconds till I start connecting your call')
    invalid_input_message = fields.Text(default='We received wrong input. Please try again!')
    gather_digits = fields.Integer(required=True, default=1)
    choices = fields.One2many('connect.voiceml.callflow_choice', 'callflow')
    ring_users = fields.Many2many('connect.user')
    record_calls = fields.Boolean()
    voicemail_prompt = fields.Text()
    voicemail_enabled = fields.Boolean()
    gather_action_url = fields.Char(compute='_get_gather_action_url')

    def create_extension(self):
        self.ensure_one()
        return self.env['connect.voiceml.exten'].create_extension(self, self._name)

    @api.model
    def _get_language_selection(self):
        # Deliberate copy of connect_twilio / connect_telnyx / core lists
        # (ADR-031/ADR-037). Keep all four in sync when editing.
        return [
            ('ca-ES', 'Catalan (Spain)'),
            ('cs-CZ', 'Czech'),
            ('da-DK', 'Danish'),
            ('de-DE', 'German'),
            ('en-GB', 'English (UK)'),
            ('en-US', 'English (US)'),
            ('es-ES', 'Spanish (Spain)'),
            ('es-MX', 'Spanish (Mexico)'),
            ('fi-FI', 'Finnish'),
            ('fr-FR', 'French'),
            ('hu-HU', 'Hungarian'),
            ('is-IS', 'Icelandic'),
            ('it-IT', 'Italian'),
            ('nl-BE', 'Dutch (Belgium)'),
            ('nl-NL', 'Dutch (Netherlands)'),
            ('pl-PL', 'Polish'),
            ('pt-BR', 'Portuguese (Brazil)'),
            ('pt-PT', 'Portuguese (Portugal)'),
            ('ro-RO', 'Romanian'),
            ('ru-RU', 'Russian'),
            ('sk-SK', 'Slovak'),
            ('sv-SE', 'Swedish'),
            ('tr-TR', 'Turkish'),
            ('uk-UA', 'Ukrainian'),
            ('vi-VN', 'Vietnamese'),
            ('zh-CN', 'Chinese (Mandarin)'),
        ]

    def _get_gather_action_url(self):
        api_url = self.env['connect.settings'].get_param('api_url')
        for rec in self:
            rec.gather_action_url = urljoin(
                api_url, 'voiceml/webhook/callflow/{}/gather'.format(rec.id))

    @api.model
    def gather_action(self, flow_id, request):
        callflow = self.browse(flow_id)
        choice = callflow.choices.filtered(
            lambda x: x.choice_digits == request.get('Digits')
            or (x.speech and request.get('SpeechResult')
                and x.speech in request.get('SpeechResult', '')))
        if not choice:
            return callflow.render(request=request, params={'invalid_input': True})
        return choice[0].exten.render(request=request)

    def _get_gather_hints(self):
        self.ensure_one()
        hints = (self.gather_hints or '').strip()
        if hints and 'speech' in (self.gather_input_type or ''):
            return hints
        return None

    def render(self, request={}, params={}):
        self.ensure_one()
        api_url = self.env['connect.settings'].sudo().get_param('api_url')
        status_url = urljoin(api_url, 'voiceml/webhook/callstatus')
        action_url = urljoin(api_url, 'voiceml/webhook/{}/call_action/{}'.format(self._name, self.id))
        record_status_url = urljoin(api_url, 'voiceml/webhook/recordingstatus')
        invalid_input = params.get('invalid_input')
        response = TwiMLResponse()
        if invalid_input:
            response.say(self.invalid_input_message, language=self.language, voice=self.voice)
        if self.prompt_message and self.gather_input:
            gather = response.gather(
                action=self.gather_action_url,
                method='POST',
                timeout=self.gather_timeout,
                numDigits=str(self.gather_digits),
                input=self.gather_input_type,
                language=self.language,
                hints=self._get_gather_hints(),
            )
            gather.say(self.prompt_message, language=self.language, voice=self.voice)
        elif self.prompt_message:
            response.say(self.prompt_message, language=self.language, voice=self.voice)
        if self.ring_users:
            callerId = request.get('Caller') or ''
            if callerId.startswith('sip:') or callerId.startswith('client:'):
                callerId = self.env['connect.voiceml.outgoing_callerid'].sudo().search(
                    [('is_default', '=', True)], limit=1).number
                if not callerId:
                    response.say('You must configure a default number for caller ID!')
                    return response.to_string()
            dial_kwargs = {'callerId': callerId, 'action': action_url}
            if self.record_calls:
                dial_kwargs.update({
                    'record': 'record-from-answer-dual',
                    'recordingStatusCallback': record_status_url,
                })
            dial = response.dial(**dial_kwargs)
            for user in self.ring_users:
                dial.sip(
                    'sip:{}'.format(user.uri),
                    statusCallbackEvent='answered completed',
                    statusCallback=status_url,
                )
        else:
            if self.voicemail_enabled and self.voicemail_prompt:
                response.pause(length=1)
                response.say(self.voicemail_prompt, language=self.language, voice=self.voice)
                response.verb('Record', maxLength=120, finishOnKey='#', playBeep=True)
            else:
                response.say('This callflow has no actions! Goodbye!')
                response.pause(length=1)
                response.hangup()
        return response.to_string()

    @api.model
    def on_call_action(self, flow_id, request):
        response = TwiMLResponse()
        if request.get('DialCallStatus') != 'completed':
            callflow = self.browse(flow_id)
            if callflow.voicemail_enabled and callflow.voicemail_prompt:
                response.pause(length=1)
                response.say(callflow.voicemail_prompt, language=callflow.language, voice=callflow.voice)
                response.verb('Record', maxLength=120, finishOnKey='#', playBeep=True)
            else:
                response.say('Sorry, I could not connect your call. Goodbye!')
                response.pause(length=1)
                response.hangup()
        else:
            response.hangup()
        return response.to_string()


class CallflowChoice(models.Model):
    _name = 'connect.voiceml.callflow_choice'
    _description = 'VoiceML Callflow Choice'

    callflow = fields.Many2one('connect.voiceml.callflow', required=True, ondelete='cascade')
    choice_digits = fields.Char(required=True)
    exten = fields.Many2one('connect.voiceml.exten', ondelete='restrict', required=True)
    speech = fields.Char()
