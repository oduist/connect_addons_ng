# -*- coding: utf-8 -*-
import json
import logging

from odoo import models, api

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)

IGNORE_ERROR_CODES = ['32009']


class Call(models.Model):
    _inherit = 'connect.call'

    @api.model
    def on_call_action(self, params):
        from .twiml_builder import TwiMLResponse
        debug(self, 'On call action: %s' % params)
        response = TwiMLResponse()
        response.hangup()
        return response.to_string()

    @api.model
    def on_call_status(self, params):
        """VoiceML webhook adapter: map params, delegate to core."""
        self = self.sudo()
        channel = self.env['connect.channel'].on_call_status(params)
        if not channel:
            logger.error('No channel returned from on_call_status!')
            return False

        error_data = None
        if (params.get('ErrorCode')
                and params.get('ErrorCode') not in IGNORE_ERROR_CODES):
            error_data = {
                'error_code': params.get('ErrorCode'),
                'error_message': params.get('ErrorMessage'),
            }

        call_id = self.process_call_event(channel, error_data)

        if error_data and channel.call and channel.call.direction == 'outgoing':
            user = channel.caller_user or channel.call.caller_user
            if user:
                self.env['connect.settings'].connect_notify(
                    notify_uid=user.id,
                    title="Call Error",
                    message=params.get('ErrorMessage', ''),
                    warning=True,
                )
        return call_id

    @api.model
    def on_vm_recording_status(self, params):
        debug(self.sudo(), 'On voicemail recording status: %s' % json.dumps(params, indent=2))
        channel = self.sudo().env['connect.channel'].search(
            [('sid', '=', params['CallSid'])])
        if channel and channel.call:
            channel.call.write({
                'voicemail_url': params.get('RecordingUrl'),
                'voicemail_duration': int(params.get('RecordingDuration', 0)),
            })
        return True
