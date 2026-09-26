# -*- coding: utf-8 -*-
import json
import logging

from odoo import models, api

from odoo.addons.connect.models.settings import debug
from .settings import MAX_EXTEN_LEN

logger = logging.getLogger(__name__)

VOICEML_LIVE_RECORDING_STATUSES = ('in-progress', 'processing', 'paused')


class Channel(models.Model):
    _inherit = 'connect.channel'

    @api.model
    def on_call_status(self, params):
        """VoiceML webhook adapter: map params and delegate to core."""
        debug(self, 'On channel status: %s' % json.dumps(params, indent=2))
        generic = self._map_voiceml_params(params)
        return self.process_channel_event(generic)

    def _strip_exten_plus(self, number):
        if not isinstance(number, str) or not number.startswith('+'):
            return number
        candidate = number[1:]
        if not candidate.isdigit() or len(candidate) > MAX_EXTEN_LEN:
            return number
        exten = self.env['connect.voiceml.exten'].sudo().search(
            [('number', '=', candidate)], limit=1)
        return candidate if exten else number

    def _map_voiceml_params(self, params):
        return {
            'sid': params['CallSid'],
            'caller': self._strip_exten_plus(params.get('Caller')),
            'called': self._strip_exten_plus(params.get('Called')),
            'to': params.get('To'),
            'technical_direction': params.get('Direction'),
            'status': params.get('CallStatus'),
            'duration': int(params.get('CallDuration', 0)),
            'call_type': 'phone',
            'parent_sid': params.get('ParentCallSid'),
        }
