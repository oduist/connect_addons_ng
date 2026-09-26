# -*- coding: utf-8 -*-
import json
import logging

from odoo import fields, models, api

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)


class Recording(models.Model):
    _inherit = 'connect.recording'

    @api.model
    def prepare_data(self, rec):
        data = {}
        for field in [
            'sid', 'call_sid', 'media_url', 'price', 'price_unit',
            'duration', 'source', 'start_time', 'status',
        ]:
            data[field] = getattr(rec, field, None)
        channel = self.env['connect.channel'].search([('sid', '=', rec.call_sid)])
        data['call'] = channel.call.id if channel else False
        data['channel'] = channel.id if channel else False
        return data

    def sync(self):
        client = self.env['connect.settings'].get_client()
        for rec in self:
            if not rec.sid:
                continue
            try:
                recording = client.recordings.get(rec.sid)
                rec.write(self.prepare_data(recording))
            except Exception as e:
                logger.exception('Recording fetch error: %s', e)

    @api.model
    def on_recording_status(self, params):
        self = self.sudo()
        debug(self, 'On recording status: %s' % json.dumps(params, indent=2))
        data = {
            'sid': params['RecordingSid'],
            'call_sid': params['CallSid'],
            'duration': params.get('RecordingDuration'),
            'status': params['RecordingStatus'],
        }
        channel = self.env['connect.channel'].search(
            [('sid', '=', params['CallSid'])], limit=1)
        if channel:
            call = channel.call
            data['channel'] = channel.id
            data['call'] = call.id
            data['partner'] = call.partner.id
            data['caller_number'] = call.caller
            data['called_number'] = call.called
        client = self.env['connect.settings'].get_client()
        try:
            recording = client.recordings.get(data['sid'])
            data.update(self.prepare_data(recording))
        except Exception as e:
            logger.exception('Recording fetch error: %s', e)
        self.create(data)
        return True
