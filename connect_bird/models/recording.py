# -*- coding: utf-8 -*-
import base64
import logging
from datetime import timedelta

import httpx

from odoo import fields, models, api

from .call import BIRD_RECORDING_MAX_ATTEMPTS

logger = logging.getLogger(__name__)


class Recording(models.Model):
    _inherit = 'connect.recording'

    def fetch_bird_call_recordings(self, call):
        """Fetch and store all recordings of a Bird call.

        Download links are expected to be short-lived pre-signed URLs, so
        the audio is downloaded immediately and stored as an attachment.
        The endpoint path is confirmed against the live platform (the
        voice API is present but not yet publicly documented).
        Returns the number of new recordings.
        """
        settings = self.env['connect.settings']
        data = settings.bird_request(
            'GET', '/voice/calls/{}/recordings'.format(call.bird_call_id),
            raise_exc=False)
        if data is False:
            return 0
        items = data.get('data', data.get('recordings', [])) or []
        fetched = 0
        for item in items:
            rec_id = item.get('id')
            url = item.get('url') or item.get('media_url')
            if not rec_id or not url:
                continue
            if item.get('status') and item['status'] not in (
                    'available', 'completed', 'done'):
                continue
            if self.sudo().search([('sid', '=', rec_id)], limit=1):
                continue
            try:
                res = httpx.get(url, timeout=30, follow_redirects=True)
                res.raise_for_status()
                audio = res.content
            except httpx.HTTPError as e:
                logger.warning('Bird recording %s download failed: %s',
                               rec_id, e)
                continue
            first_channel = call.channels.sorted(key='id')[:1]
            self.sudo().create({
                'sid': rec_id,
                'call_sid': call.bird_call_id,
                'call': call.id,
                'channel': first_channel.id,
                'partner': call.partner.id,
                'caller_number': call.caller,
                'called_number': call.called,
                'duration': int(item.get('duration') or 0),
                'status': item.get('status'),
                'source': 'bird',
                'media_url': url,
                'recording_attachment': base64.b64encode(audio),
                'recording_filename': '{}.{}'.format(
                    rec_id, item.get('format') or 'mp3'),
            })
            fetched += 1
        return fetched

    def get_transcript(self, fail_silently=False):
        """Override: the stored pre-signed URL may be long dead by the
        time a deferred transcription runs — refresh it from the API
        first. Transcription itself is unaffected when the recording is
        already stored as an attachment.
        """
        self.ensure_one()
        if self.source == 'bird' and self.sid and self.call_sid:
            data = self.env['connect.settings'].bird_request(
                'GET', '/voice/calls/{}/recordings'.format(self.call_sid),
                raise_exc=False)
            if data:
                for item in data.get('data', data.get('recordings', [])) or []:
                    if item.get('id') == self.sid and (
                            item.get('url') or item.get('media_url')):
                        self.with_context(tracking_disable=True).write({
                            'media_url': item.get('url')
                            or item.get('media_url')})
                        break
        return super().get_transcript(fail_silently=fail_silently)

    @api.model
    def _cron_fetch_bird_recordings(self, limit=20):
        """Pick up recordings for recently completed Bird calls.

        Recordings lag call completion, so each call is retried up to
        BIRD_RECORDING_MAX_ATTEMPTS cron passes before giving up.
        """
        calls = self.env['connect.call'].sudo().search([
            ('bird_recording_pending', '=', True),
            ('bird_call_id', '!=', False),
            ('create_date', '>', fields.Datetime.now() - timedelta(days=30)),
        ], limit=limit)
        for call in calls:
            try:
                fetched = self.fetch_bird_call_recordings(call)
            except Exception as e:
                logger.exception(
                    'Bird recording fetch failed for call %s: %s', call.id, e)
                fetched = 0
            if fetched or call.bird_recording_attempts >= BIRD_RECORDING_MAX_ATTEMPTS:
                call.write({'bird_recording_pending': False})
            else:
                call.write({
                    'bird_recording_attempts': call.bird_recording_attempts + 1,
                })
        return True
