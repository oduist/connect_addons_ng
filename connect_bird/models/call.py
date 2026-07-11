# -*- coding: utf-8 -*-
import logging

from odoo import fields, models, api

from odoo.addons.connect.models.call import CALL_END_STATUSES

logger = logging.getLogger(__name__)

# Give up fetching recordings for a call after this many cron passes.
BIRD_RECORDING_MAX_ATTEMPTS = 10


class Call(models.Model):
    _inherit = 'connect.call'

    bird_call_id = fields.Char('Bird Call ID', index=True, readonly=True)
    bird_recording_pending = fields.Boolean(default=False, copy=False)
    bird_recording_attempts = fields.Integer(default=0, copy=False)

    @api.model
    def on_bird_call_event(self, payload, event):
        """Entry point of the voice webhooks: channel upsert, then the
        shared call pipeline, then Bird-specific bookkeeping.
        """
        self = self.sudo()
        channel = self.env['connect.channel'].on_bird_call_event(
            payload, event)
        error_data = None
        if payload.get('status') == 'failed':
            failure = payload.get('failure') or payload.get('error') or {}
            error_data = {
                'error_code': str(failure.get('code', '') or ''),
                'error_message': (failure.get('description')
                                  or failure.get('message') or 'failed'),
            }
        call_id = self.process_call_event(channel, error_data)
        call = channel.call
        if call and not call.bird_call_id:
            # The first channel's sid identifies the call towards the
            # Recordings API.
            call.bird_call_id = channel.sid
        if (call and channel.status in CALL_END_STATUSES
                and not call.bird_recording_pending):
            # Recordings lag call completion: flag the call for the fetch
            # cron instead of querying inline. Calls without recordings
            # simply exhaust their attempts.
            call.write({
                'bird_recording_pending': True,
                'bird_recording_attempts': 0,
            })
        return call_id
