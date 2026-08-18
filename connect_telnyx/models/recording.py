# -*- coding: utf-8 -*-
import base64
import logging

import requests

from odoo import fields, models, api

from odoo.addons.connect.models.settings import debug

from .utils import format_telnyx_debug_payload

logger = logging.getLogger(__name__)

MAX_AI_RECORDING_BYTES = 100 * 1024 * 1024


class Recording(models.Model):
    _inherit = 'connect.recording'

    telnyx_recording_id = fields.Char(
        string='Telnyx Recording ID', readonly=True, copy=False, index=True,
    )

    def telnyx_attach_ai_audio(self, call_control_id):
        """Attach the Telnyx AI call recording without re-transcribing it."""
        self.ensure_one()
        if self.recording_attachment or not call_control_id:
            return self
        response = self.env['connect.settings'].sudo().telnyx_api_request(
            'GET', 'recordings', params={
                'filter[call_control_id]': call_control_id,
                'page[size]': 10,
            },
        )
        recordings = response.get('data', response)
        if not isinstance(recordings, list):
            return self
        recording = next(
            (
                item for item in recordings
                if item.get('status') == 'completed'
                and item.get('call_control_id') == call_control_id
            ),
            None,
        )
        if not recording:
            return self
        urls = recording.get('download_urls') or {}
        media_url = urls.get('mp3') or urls.get('wav')
        if not media_url:
            return self
        response = requests.get(media_url, stream=True, timeout=30)
        response.raise_for_status()
        content_length = int(response.headers.get('Content-Length') or 0)
        if content_length > MAX_AI_RECORDING_BYTES:
            raise ValueError('Telnyx AI recording exceeds the download limit.')
        audio = bytearray()
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            audio.extend(chunk)
            if len(audio) > MAX_AI_RECORDING_BYTES:
                raise ValueError(
                    'Telnyx AI recording exceeds the download limit.')
        recording_id = recording.get('id') or ''
        extension = 'mp3' if urls.get('mp3') else 'wav'
        self.with_context(
            skip_transcription=True, tracking_disable=True,
        ).write({
            'telnyx_recording_id': recording_id,
            'recording_attachment': base64.b64encode(bytes(audio)),
            'recording_filename': '{}.{}'.format(
                recording_id or self.sid or 'telnyx-ai', extension),
            'duration': int(
                recording.get('duration_millis') or 0) // 1000,
            'media_url': False,
            'transcription_pending': False,
        })
        return self

    @api.model
    def telnyx_prepare_data(self, rec):
        """Map a Telnyx recording resource to connect.recording values."""
        urls = getattr(rec, 'download_urls', None)
        media_url = ''
        if urls:
            media_url = getattr(urls, 'mp3', None) or getattr(urls, 'wav', None) or ''
        data = {
            'sid': rec.id,
            'media_url': media_url,
            'duration': int(getattr(rec, 'duration_millis', 0) or 0) // 1000,
            'source': getattr(rec, 'source', None) or '',
            'status': getattr(rec, 'status', None) or '',
        }
        call_sid = (
            getattr(rec, 'call_control_id', None)
            or getattr(rec, 'call_leg_id', None)
            or ''
        )
        channel = self.env['connect.channel']
        if call_sid:
            channel = channel.search([('sid', '=', call_sid)], limit=1)
        if channel and channel.call:
            data.update({
                'call_sid': call_sid,
                'call': channel.call.id,
                'channel': channel.id,
            })
        return data

    @api.model
    def on_telnyx_recording_status(self, params):
        self = self.sudo()
        debug(
            self,
            'On recording status: %s' % format_telnyx_debug_payload(params),
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
