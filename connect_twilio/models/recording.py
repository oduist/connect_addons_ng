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
            'sid',
            'call_sid',
            'media_url',
            'price',
            'price_unit',
            'duration',
            'source',
            'start_time',
            'status',
        ]:
            data[field] = getattr(rec, field)
            if field in ['start_time', 'date_created', 'date_updated']:
                data[field] = data[field].utcnow()
        channel = self.env['connect.channel'].search(
            [('sid', '=', rec.call_sid)]
        )
        data['call'] = channel.call.id
        data['channel'] = channel.id
        return data

    def sync(self):
        client = self.env['connect.settings'].get_client()
        for rec in self:
            if not rec.media_url:
                continue
            recording = client.recordings(rec.sid).fetch()
            data = self.prepare_data(recording)
            rec.write(data)

    @api.model
    def on_recording_status(self, params):
        self = self.sudo()
        debug(
            self,
            'On recording status: %s' % json.dumps(params, indent=2),
        )
        data = {
            'sid': params['RecordingSid'],
            'call_sid': params['CallSid'],
            'duration': params['RecordingDuration'],
            'status': params['RecordingStatus'],
        }
        channel = self.env['connect.channel'].search(
            [('sid', '=', params['CallSid'])], limit=1
        )
        called_user = (
            channel.search(
                [
                    '|',
                    ('sid', '=', params['CallSid']),
                    ('parent_channel', '=', channel.id),
                    ('called_user', '!=', False),
                ],
                limit=1,
            ).called_user
        )
        if channel:
            call = channel.call
            data['channel'] = channel.id
            data['call'] = call.id
            data['partner'] = call.partner.id
            data['called_user'] = called_user.id
            data['caller_number'] = call.caller
            data['called_number'] = call.called
        # Fetch recording
        client = self.env['connect.settings'].get_client()
        try:
            recording = client.recordings(data['sid']).fetch()
            data.update(self.prepare_data(recording))
        except Exception as e:
            logger.exception('Recording fetch error: %s', e)
        self.create(data)
        return True
