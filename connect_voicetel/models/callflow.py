# -*- coding: utf-8 -*-
import logging
from odoo import fields, models, api
from .voiceml_response import Gather, VoiceResponse, Dial
from odoo.addons.connect.models.settings import debug
from .voiceml import pretty_xml

logger = logging.getLogger(__name__)


class CallFlow(models.Model):
    _name = 'connect.voicetel.callflow'
    _description = 'VoiceTel Call Flow'
    _order = 'name asc'

    name = fields.Char(required=True)
    exten = fields.Many2one('connect.voicetel.exten', ondelete='set null', readonly=True)
    exten_number = fields.Char(related='exten.number', store=True)
    language = fields.Selection(
        selection=lambda self: self._get_language_selection(),
        default='en-US',
        required=True,
        string='Language',
    )
    voice = fields.Char(required=True, default='Woman')
    gather_input = fields.Boolean()
    gather_input_type = fields.Selection(string='Input Type',
        selection=[
            ('dtmf', 'DTMF'),
            ('speech', 'Speech'),
            ('dtmf speech', 'DTMF + speech'),
        ],
        required=True, default='dtmf')
    gather_timeout = fields.Integer(string='Timeout', default=5)
    gather_hints = fields.Char('Hints', default='This is a phrase I expect to hear, department name or extension number')
    prompt_message = fields.Text('Prompt Message',
        default='Welcome to our company! Please enter the extension number of person '
                'you wish to dial or wait 5 seconds till I start connecting your call')
    invalid_input_message = fields.Text(default='We received wrong input. Please try again!')
    gather_digits = fields.Integer(required=True, default=1)
    choices = fields.One2many('connect.voicetel.callflow_choice', 'callflow')
    ring_users = fields.Many2many('connect.user')
    record_calls = fields.Boolean()
    voicemail_prompt = fields.Text(
        help='Message played before recording callflow voicemail. '
             'Callflow voicemail takes precedence over user voicemail inside '
             'callflows; direct user routing keeps user voicemail behavior.')
    voicemail_enabled = fields.Boolean(
        help='Enable callflow voicemail after no callflow action handles the '
             'caller. Requires a voicemail prompt.')
    gather_action_url = fields.Char(compute='_get_gather_action_url')

    def create_extension(self):
        self.ensure_one()
        return self.env['connect.voicetel.exten'].create_extension(self, self._name)

    @api.model
    def _get_language_selection(self):
        """Languages offered for <Say>.

        Codes are BCP-47 and are passed verbatim to the VoiceML Say verb.
        Duplicated by design (ADR-031/ADR-037/ADR-066) in the connect_twilio,
        connect_freeswitch and connect_telnyx callflows and in core
        connect.user -- keep all five lists in sync when editing.
        """
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
        settings = self.env['connect.settings'].sudo()
        for rec in self:
            rec.gather_action_url = settings.voicetel_webhook_url(
                'voicetel/webhook/callflow/{}/gather'.format(rec.id))

    @api.model
    def gather_action(self, flow_id, request):
        callflow = self.browse(flow_id)
        choice = callflow.choices.filtered(
            lambda x: x.choice_digits == request.get('Digits') or
                (x.speech and request.get('SpeechResult') and x.speech in
                request.get('SpeechResult', '')))
        if not choice:
            logger.warning('Gather choice digits: %s, speech: %s not found in Call Flow %s',
                request.get('Digits'), request.get('SpeechResult'), callflow.name)
            return callflow.render(request=request, params={'invalid_input': True})
        return choice[0].exten.render(request=request)

    def _get_gather_hints(self):
        self.ensure_one()
        hints = (self.gather_hints or '').strip()
        if hints and 'speech' in (self.gather_input_type or ''):
            return hints
        return None

    def render(self, request=None, params=None):
        self.ensure_one()
        request = dict(request or {})
        params = dict(params or {})
        settings = self.env['connect.settings'].sudo()
        voicemail_record_status_url = settings.voicetel_webhook_url(
            'voicetel/webhook/vm_recordingstatus')
        status_url = settings.voicetel_webhook_url('voicetel/webhook/callstatus')
        action_url = settings.voicetel_webhook_url(
            'voicetel/webhook/{}/call_action/{}'.format(self._name, self.id))
        record_status_url = settings.voicetel_webhook_url('voicetel/webhook/recordingstatus')
        invalid_input = params.get('invalid_input')
        response = VoiceResponse()
        if invalid_input:
            self.get_gather_invalid_input_message(response)
        if self.prompt_message and self.gather_input:
            gather = Gather(
                action=self.gather_action_url,
                method='POST',
                timeout=self.gather_timeout,
                numDigits=str(self.gather_digits),
                input=self.gather_input_type,
                language=self.language,
                hints=self._get_gather_hints(),
            )
            self.get_prompt_message(gather)
            response.append(gather)
        elif self.prompt_message:
            self.get_prompt_message(response)
        if self.ring_users:
            callerId = request.get('Caller') or ''
            if callerId.startswith('sip:') or callerId.startswith('client:'):
                callerId = self.env['connect.voicetel.outgoing_callerid'].sudo().search(
                    [('is_default', '=', True)], limit=1).number
                if not callerId:
                    response = VoiceResponse()
                    response.say('Your must configure a default number for caller ID!')
                    return response
            if self.record_calls:
                dial = Dial(callerId=callerId, action=action_url,
                    record='record-from-answer-dual', recordingStatusCallback=record_status_url)
            else:
                dial = Dial(callerId=callerId, action=action_url)
            for user in self.ring_users:
                # One <Sip> per user: the registrar rings every device
                # registered with that credential, browser phone included.
                if user.voicetel_sip_enabled and user.voicetel_uri:
                    dial.sip('sip:{}'.format(user.voicetel_uri),
                        statusCallbackEvent='answered completed',
                        statusCallback=status_url)
            response.append(dial)
        else:
            if self.voicemail_enabled and self.voicemail_prompt:
                response.pause(length=1)
                self.get_voicemail_prompt_message(response)
                response.record(
                    maxLength=120,
                    finishOnKey='#',
                    playBeep=True,
                    recordingStatusCallback=voicemail_record_status_url)
            else:
                response.say('This callflow has no actions! Goodbye!')
                response.pause(length=1)
                response.hangup()
        debug(self, pretty_xml(str(response)))
        return response

    def get_prompt_message(self, response):
        debug(self, 'Saying prompt message for Call Flow {}'.format(self.name))
        response.say(self.prompt_message, language=self.language, voice=self.voice)

    def get_gather_invalid_input_message(self, response):
        response.say(self.invalid_input_message, language=self.language, voice=self.voice)

    def get_voicemail_prompt_message(self, response):
        response.say(self.voicemail_prompt, language=self.language, voice=self.voice)

    @api.model
    def voicetel_on_call_action(self, flow_id, request):
        response = VoiceResponse()
        if request.get('DialCallStatus') != 'completed':
            callflow = self.browse(flow_id)
            if callflow.voicemail_enabled and callflow.voicemail_prompt:
                record_status_url = self.env['connect.settings'].sudo().voicetel_webhook_url(
                    'voicetel/webhook/vm_recordingstatus')
                response.pause(length=1)
                callflow.get_voicemail_prompt_message(response)
                response.record(
                    maxLength=120,
                    finishOnKey='#',
                    playBeep=True,
                    recordingStatusCallback=record_status_url)
            else:
                response.say('Sorry, I could not connect your call. Goodbye!')
                response.pause(length=1)
                response.hangup()
        else:
            response.hangup()
        debug(self, pretty_xml(str(response)))
        return response


class CallflowChoice(models.Model):
    _name = 'connect.voicetel.callflow_choice'
    _description = 'VoiceTel Callflow Choice'

    callflow = fields.Many2one('connect.voicetel.callflow', required=True, ondelete='cascade')
    choice_digits = fields.Char(required=True)
    exten = fields.Many2one('connect.voicetel.exten', ondelete='restrict', required=True)
    speech = fields.Char()
