# -*- coding: utf-8 -*-
import json
import logging

from odoo import models, api

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)


class Recording(models.Model):
    _inherit = 'connect.recording'

    @api.model
    def telnyx_prepare_data(self, rec):
        """Map a Telnyx recording resource to connect.recording values."""
        urls = getattr(rec, 'download_urls', None)
        media_url = ''
        if urls:
            media_url = getattr(urls, 'mp3', None) or getattr(urls, 'wav', None) or ''
        data = {
            'sid': rec.id,
            'call_sid': getattr(rec, 'call_leg_id', None) or '',
            'media_url': media_url,
            'duration': int(getattr(rec, 'duration_millis', 0) or 0) // 1000,
            'source': getattr(rec, 'source', None) or '',
            'status': getattr(rec, 'status', None) or '',
        }
        channel = self.env['connect.channel'].search(
            [('sid', '=', data['call_sid'])]
        )
        data['call'] = channel.call.id
        data['channel'] = channel.id
        return data

    @api.model
    def on_telnyx_recording_status(self, params):
        self = self.sudo()
        debug(
            self,
            'On recording status: %s' % json.dumps(params, indent=2),
        )
        data = {
            'sid': params['RecordingSid'],
            'call_sid': params['CallSid'],
            'media_url': params.get('RecordingUrl'),
            'duration': params.get('RecordingDuration'),
            'status': params.get('RecordingStatus'),
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
        # Fetch the recording resource for the durable download URL
        try:
            client = self.env['connect.settings'].get_telnyx_client()
            recording = client.recordings.retrieve(data['sid'])
            data.update(self.telnyx_prepare_data(recording.data))
        except Exception as e:
            logger.exception('Recording fetch error: %s', e)
        self.create(data)
        return True
