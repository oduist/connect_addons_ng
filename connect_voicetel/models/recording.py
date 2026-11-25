# -*- coding: utf-8 -*-
import base64
import json
import logging

import requests

from odoo import models, api

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)

# VoiceML serves the WAV locally only until it is uploaded to the tenant's
# own bucket or cleaned up, so the download runs in the callback itself.
RECORDING_DOWNLOAD_TIMEOUT = 30


class Recording(models.Model):
    _inherit = 'connect.recording'

    @api.model
    def prepare_voicetel_data(self, rec):
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
            value = getattr(rec, field, None)
            if field == 'start_time' and value is not None and hasattr(value, 'replace'):
                value = value.replace(tzinfo=None)
            data[field] = value
        channel = self.env['connect.channel'].search(
            [('sid', '=', rec.call_sid)], limit=1
        )
        data['call'] = channel.call.id
        data['channel'] = channel.id
        return data

    @api.model
    def _voicetel_media_url(self, recording_url):
        """The RecordingUrl VoiceML reports, as an absolute URL.

        VoiceML emits Twilio's extension-less form; a relative URI is
        completed with the configured API host.
        """
        url = (recording_url or '').strip()
        if url and not url.lower().startswith('http'):
            url = 'https://{}/{}'.format(
                self.env['connect.settings']._voicetel_api_host(), url.lstrip('/'))
        return url

    def voicetel_download(self):
        """Pull the audio into the record while VoiceML still serves it.

        A failure is logged and the media URL is kept: the proxy then fetches
        the audio with the account credentials for as long as VoiceML keeps
        the file (or redirects to the tenant's bucket).
        """
        settings = self.env['connect.settings'].sudo()
        for rec in self:
            if rec.recording_attachment or not rec.media_url:
                continue
            try:
                response = requests.get(
                    rec.media_url,
                    auth=settings.get_media_auth(rec.media_url),
                    timeout=RECORDING_DOWNLOAD_TIMEOUT,
                    stream=True,
                )
                response.raise_for_status()
                content = response.content
                if not content:
                    raise ValueError('empty recording body')
                content_type = (response.headers.get('Content-Type') or '').lower()
                extension = '.mp3' if 'mpeg' in content_type else '.wav'
                rec.with_context(tracking_disable=True).write({
                    'recording_attachment': base64.b64encode(content),
                    'recording_filename': '{}{}'.format(rec.sid or 'recording', extension),
                })
                debug(self, 'Downloaded VoiceML recording {} ({} bytes)'.format(
                    rec.sid, len(content)))
            except Exception as e:
                logger.warning(
                    'Could not download VoiceML recording %s from %s: %s',
                    rec.sid, rec.media_url, e)
        return True

    @api.model
    def on_voicetel_recording_status(self, params):
        self = self.sudo()
        debug(
            self,
            'On recording status: %s' % json.dumps(params, indent=2),
        )
        if params.get('RecordingStatus') not in (None, 'completed'):
            # in-progress / absent carry no audio to store.
            return True
        data = {
            'sid': params['RecordingSid'],
            'call_sid': params['CallSid'],
            'duration': int(params.get('RecordingDuration') or 0),
            'status': params.get('RecordingStatus') or 'completed',
            'media_url': self._voicetel_media_url(params.get('RecordingUrl')),
            'source': params.get('RecordingSource'),
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
        existing = self.search([('sid', '=', data['sid'])], limit=1)
        if existing:
            existing.write(data)
            recording = existing
        else:
            recording = self.create(data)
        recording.voicetel_download()
        return True
