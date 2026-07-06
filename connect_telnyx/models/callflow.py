# -*- coding: utf-8 -*-
import logging
from urllib.parse import urljoin
from odoo import fields, models, api
from odoo.addons.connect.models.settings import debug
from .texml_response import Gather, VoiceResponse, Dial, pretty_xml

logger = logging.getLogger(__name__)


class CallFlow(models.Model):
    _name = 'connect.telnyx.callflow'
    _description = 'Telnyx Call Flow'
    _order = 'name asc'

    name = fields.Char(required=True)
    exten = fields.Many2one('connect.telnyx.exten', ondelete='set null', readonly=True)
    exten_number = fields.Char(related='exten.number', store=True)
    language = fields.Selection(
        selection=lambda self: self._get_language_selection(),
        default='en-US',
        required=True,
        string='Language',
    )
    voice = fields.Char(required=True, default='Polly.Joanna')
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
    choices = fields.One2many('connect.telnyx.callflow_choice', 'callflow')
    ring_users = fields.Many2many('connect.user')
    record_calls = fields.Boolean()
    voicemail_prompt = fields.Text()
    voicemail_enabled = fields.Boolean()
    gather_action_url = fields.Char(compute='_get_gather_action_url')

    def create_extension(self):
        self.ensure_one()
        return self.env['connect.telnyx.exten'].create_extension(self, self._name)

    @api.model
    def _get_language_selection(self):
        """Languages supported by Telnyx TeXML Say (AWS Polly voices).

        Codes are BCP-47 and are passed verbatim to TeXML Say. Duplicated
        in connect_twilio and connect_freeswitch by design — the providers
        are fully independent; keep the lists in sync when editing
        (ADR-031/ADR-032).
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
        api_url = self.env['connect.settings'].get_param('api_url')
        for rec in self:
            rec.gather_action_url = urljoin(api_url,
                'telnyx/webhook/callflow/{}/gather'.format(rec.id))

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

    def render(self, request={}, params={}):
        self.ensure_one()
        api_url = self.env['connect.settings'].sudo().get_param('api_url')
        voicemail_record_status_url = urljoin(api_url,
            'telnyx/webhook/vm_recordingstatus')
        status_url = urljoin(api_url, 'telnyx/webhook/callstatus')
        action_url = urljoin(api_url, 'telnyx/webhook/{}/call_action/{}'.format(self._name, self.id))
        record_status_url = urljoin(api_url, 'telnyx/webhook/recordingstatus')
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
                language=self.language
            )
            self.get_prompt_message(gather)
            response.append(gather)
        elif self.prompt_message:
            self.get_prompt_message(response)
        if self.ring_users:
            callerId = request.get('Caller')
            if callerId and callerId.startswith('sip:'):
                callerId = self.env['connect.telnyx.outgoing_callerid'].sudo().search(
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
                callflows = self.env['connect.telnyx.user_callflow'].sudo().search(
                    [('callflow_type', 'in', ['sip', 'client']), ('user', '=', user.id)], order='prio')
                for callflow in callflows:
                    if callflow.callflow_type == 'sip':
                        uri = user.telnyx_sip_username
                    else:
                        uri = user.telnyx_client_username
                    if not uri:
                        continue
                    dial.sip('sip:{}@sip.telnyx.com'.format(uri),
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
    def on_call_action(self, flow_id, request):
        response = VoiceResponse()
        if request.get('DialCallStatus') != 'completed':
            callflow = self.browse(flow_id)
            if callflow.voicemail_prompt:
                api_url = self.env['connect.settings'].sudo().get_param('api_url')
                record_status_url = urljoin(api_url, 'telnyx/webhook/vm_recordingstatus')
                response.pause(length=1)
                response.say(callflow.voicemail_prompt, language=callflow.language, voice=callflow.voice)
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
    _name = 'connect.telnyx.callflow_choice'
    _description = 'Telnyx Callflow Choice'

    callflow = fields.Many2one('connect.telnyx.callflow', required=True, ondelete='cascade')
    choice_digits = fields.Char(required=True)
    exten = fields.Many2one('connect.telnyx.exten', ondelete='restrict', required=True)
    speech = fields.Char()
