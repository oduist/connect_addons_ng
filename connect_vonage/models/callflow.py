# -*- coding: utf-8 -*-
import json
import logging

from odoo import fields, models, api

from odoo.addons.connect.models.settings import debug
from .channel import VONAGE_FAIL_STATUSES

logger = logging.getLogger(__name__)


class CallFlow(models.Model):
    _inherit = 'connect.callflow'

    # Vonage's input action supports speech recognition (ASR) in addition
    # to DTMF. When this module is uninstalled, callflows that used a
    # speech option fall back to DTMF.
    gather_input_type = fields.Selection(
        selection_add=[
            ('speech', 'Speech'),
            ('dtmf speech', 'DTMF + speech'),
        ],
        ondelete={'speech': 'set default', 'dtmf speech': 'set default'},
    )

    gather_action_url = fields.Char(compute='_get_gather_action_url')

    def _get_gather_action_url(self):
        for rec in self:
            rec.gather_action_url = self.env[
                'connect.settings'].get_vonage_webhook_url(
                    'callflow/{}/input'.format(rec.id))

    @api.model
    def gather_action(self, flow_id, request):
        """Input action event handler (the Twilio Gather analog)."""
        callflow = self.browse(flow_id)
        digits = (request.get('dtmf') or {}).get('digits') or ''
        speech_results = (request.get('speech') or {}).get('results') or []
        speech_text = speech_results[0].get('text') if speech_results else ''
        choice = callflow.choices.filtered(
            lambda x: (digits and x.choice_digits == digits) or
                (x.speech and speech_text and x.speech in speech_text))
        if not choice:
            logger.warning(
                'Gather choice digits: %s, speech: %s not found in '
                'Call Flow %s', digits, speech_text, callflow.name)
            return callflow.render(
                request=request, params={'invalid_input': True})
        return choice[0].exten.render(request=request)

    def render(self, request={}, params={}):
        self.ensure_one()
        request = dict(request or {})
        params = dict(params or {})
        settings = self.env['connect.settings']
        vm_recording_url = settings.get_vonage_webhook_url('vm_recording')
        action_url = settings.get_vonage_webhook_url(
            'connect.callflow/call_action/{}'.format(self.id))
        invalid_input = params.get('invalid_input')
        ncco = []
        if invalid_input:
            self.get_gather_invalid_input_message(ncco)
        if self.prompt_message and self.gather_input:
            self.get_prompt_message(ncco, barge_in=True)
            input_action = {
                'action': 'input',
                'type': self.gather_input_type.split(),
                'eventUrl': [self.gather_action_url],
                'eventMethod': 'POST',
            }
            if 'dtmf' in self.gather_input_type:
                input_action['dtmf'] = {
                    'maxDigits': self.gather_digits,
                    'timeOut': self.gather_timeout,
                }
            if 'speech' in self.gather_input_type:
                speech = {'language': self.language}
                if self.gather_hints:
                    speech['context'] = [
                        k.strip() for k in self.gather_hints.split(',')]
                input_action['speech'] = speech
            ncco.append(input_action)
            debug(self, json.dumps(ncco, indent=2))
            return ncco
        elif self.prompt_message:
            self.get_prompt_message(ncco)
        if self.ring_users:
            callerId = self.env['connect.channel']._vonage_endpoint_to_uri(
                request.get('from'))
            if callerId.startswith('sip:') or callerId.startswith('client:'):
                default_callerid = self.env[
                    'connect.outgoing_callerid'].sudo().search(
                        [('is_default', '=', True)], limit=1)
                if not default_callerid:
                    return [{
                        'action': 'talk',
                        'text': 'You must configure a default number '
                                'for caller ID!',
                    }]
                callerId = default_callerid.number
            if self.record_calls:
                ncco.append({
                    'action': 'record',
                    'format': 'mp3',
                    'split': 'conversation',
                    'eventUrl': [
                        settings.get_vonage_webhook_url('recording')],
                    'eventMethod': 'POST',
                })
            # Vonage connect takes a single endpoint, so users ring
            # sequentially in priority order: the NCCO advances to the
            # next action when a connect is unanswered (ADR-036).
            for user in self.ring_users:
                callflows = self.env['connect.user_callflow'].sudo().search(
                    [('callflow_type', '=', 'client'),
                     ('user', '=', user.id)], order='prio')
                for callflow in callflows:
                    ncco.append({
                        'action': 'connect',
                        'endpoint': [{
                            'type': 'app',
                            'user': user.username,
                        }],
                        'from': callerId.lstrip('+'),
                        'timeout': user.client_ring_timeout,
                        'eventUrl': [
                            settings.get_vonage_webhook_url('event')],
                        'eventMethod': 'POST',
                    })
            # After the last unanswered connect, fall through to
            # voicemail (or hang up).
            if self.voicemail_enabled and self.voicemail_prompt:
                self.get_voicemail_prompt_message(ncco)
                ncco.append(self._make_vm_record_action(vm_recording_url))
        else:
            if self.voicemail_enabled and self.voicemail_prompt:
                self.get_voicemail_prompt_message(ncco)
                ncco.append(self._make_vm_record_action(vm_recording_url))
            else:
                ncco.append({
                    'action': 'talk',
                    'text': 'This callflow has no actions! Goodbye!',
                    'language': self.language,
                })
        debug(self, json.dumps(ncco, indent=2))
        return ncco

    def _make_vm_record_action(self, vm_recording_url):
        return {
            'action': 'record',
            'format': 'mp3',
            'endOnKey': '#',
            'beepStart': True,
            'timeOut': 120,
            'eventUrl': [vm_recording_url],
            'eventMethod': 'POST',
        }

    def get_prompt_message(self, ncco, barge_in=False):
        debug(self, 'Saying prompt message for Call Flow {}'.format(self.name))
        action = {
            'action': 'talk',
            'text': self.prompt_message,
            'language': self.language,
        }
        if barge_in:
            action['bargeIn'] = True
        ncco.append(action)

    def get_gather_invalid_input_message(self, ncco):
        ncco.append({
            'action': 'talk',
            'text': self.invalid_input_message,
            'language': self.language,
        })

    def get_voicemail_prompt_message(self, ncco):
        ncco.append({
            'action': 'talk',
            'text': self.voicemail_prompt,
            'language': self.language,
        })

    @api.model
    def on_call_action(self, flow_id, request):
        """Synchronous connect event handler for callflow-dialed legs."""
        self.env['connect.call'].on_voice_event(request)
        if request.get('status') not in VONAGE_FAIL_STATUSES:
            return None
        ncco = []
        callflow = self.browse(flow_id)
        if callflow.voicemail_prompt:
            vm_recording_url = self.env[
                'connect.settings'].get_vonage_webhook_url('vm_recording')
            ncco.append({
                'action': 'talk',
                'text': callflow.voicemail_prompt,
                'language': callflow.language,
            })
            ncco.append(callflow._make_vm_record_action(vm_recording_url))
        else:
            ncco.append({
                'action': 'talk',
                'text': 'Sorry, I could not connect your call. Goodbye!',
            })
        debug(self, json.dumps(ncco, indent=2))
        return ncco
