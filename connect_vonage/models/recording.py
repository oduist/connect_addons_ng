# -*- coding: utf-8 -*-
import base64
import json
import logging
import os
from datetime import datetime
from tempfile import NamedTemporaryFile

from odoo import fields, models, api
from odoo.exceptions import ValidationError
from odoo.tools import config

from odoo.addons.connect.models.settings import debug
from .settings import lock_vonage_webhook

logger = logging.getLogger(__name__)


def _parse_vonage_timestamp(value):
    if not value:
        return None
    for fmt in ('%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S.%fZ',
                '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


class Recording(models.Model):
    _inherit = 'connect.recording'

    # Vonage recording URLs require application JWT auth, so they are
    # never exposed as media_url (which the core downloads with a plain
    # GET). The file is downloaded into recording_attachment instead.
    vonage_recording_url = fields.Char(readonly=True)
    vonage_downloaded = fields.Boolean(default=False)

    @api.model
    def on_recording_event(self, params, source=None):
        self = self.sudo()
        debug(self, 'On recording event: %s' % json.dumps(params, indent=2))
        recording_url = params.get('recording_url')
        if not recording_url:
            return False
        recording_uuid = params.get('recording_uuid')
        if not recording_uuid:
            logger.error('Vonage recording event has no recording_uuid.')
            return False
        lock_vonage_webhook(self.env.cr, 'recording', recording_uuid)
        if self.search_count([('sid', '=', recording_uuid)], limit=1):
            return True
        conversation_uuid = params.get('conversation_uuid')
        channel = self.env['connect.channel'].search(
            [('conversation_uuid', '=', conversation_uuid)],
            limit=1, order='id asc')
        duration = 0
        start_time = _parse_vonage_timestamp(params.get('start_time'))
        end_time = _parse_vonage_timestamp(params.get('end_time'))
        if start_time and end_time:
            duration = int((end_time - start_time).total_seconds())
        data = {
            'sid': recording_uuid,
            'call_sid': channel.sid,
            'vonage_recording_url': recording_url,
            'status': 'completed',
            'duration': duration,
            'start_time': start_time,
            'source': source,
        }
        if channel:
            call = channel.call
            data.update({
                'channel': channel.id,
                'call': call.id,
                'partner': call.partner.id,
                'called_user': channel.called_user.id,
                'caller_number': call.caller,
                'called_number': call.called,
            })
        # skip_transcription: the media is not downloaded yet; the flag is
        # set by _download_vonage_recording() once the attachment exists.
        self.with_context(skip_transcription=True).create(data)
        return True

    @api.model
    def on_vm_recording_event(self, params):
        return self.on_recording_event(params, source='voicemail')

    def _download_vonage_recording(self):
        """Download the recording with JWT auth into the attachment."""
        self.ensure_one()
        if not self.vonage_recording_url or self.vonage_downloaded:
            return True
        client = self.env['connect.settings'].get_client()
        temp_file = NamedTemporaryFile(delete=False, suffix='.mp3')
        temp_file.close()
        try:
            client.voice.download_recording(
                self.vonage_recording_url, temp_file.name)
            with open(temp_file.name, 'rb') as audio_file:
                content = audio_file.read()
            self.with_context(tracking_disable=True).write({
                'recording_attachment': base64.b64encode(content),
                'recording_filename': '{}.mp3'.format(self.sid or self.id),
                'vonage_downloaded': True,
            })
            transcript_calls = self.env['connect.settings'].sudo().get_param(
                'transcript_calls')
            if transcript_calls and not self.transcript:
                self.transcription_pending = True
            debug(self, 'Recording {} downloaded.'.format(self.id))
            return True
        except Exception as e:
            logger.error(
                'Cannot download Vonage recording %s: %s', self.id, e)
            return False
        finally:
            if os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except OSError:
                    logger.warning(
                        'Could not remove temp file %s', temp_file.name)

    @api.model
    def _cron_download_vonage_recordings(self, limit=20):
        """Download pending recordings outside the webhook request."""
        pending = self.search([
            ('vonage_recording_url', '!=', False),
            ('vonage_downloaded', '=', False),
        ], limit=limit)
        for rec in pending:
            try:
                rec._download_vonage_recording()
            except Exception:
                logger.exception(
                    'Cron download error for recording %s', rec.id)
            # The test cursor forbids commit; each download is committed
            # independently only in real cron runs.
            if not config['test_enable']:
                self.env.cr.commit()

    def get_transcript(self, fail_silently=False):
        # Core requires media_url; Vonage recordings live in the
        # attachment instead.
        self.ensure_one()
        if self.media_url or not self.recording_attachment:
            return super().get_transcript(fail_silently=fail_silently)
        openai_key = self.env['connect.settings'].sudo().get_param(
            'openai_api_key')
        if not openai_key:
            if fail_silently:
                logger.warning(
                    'OpenAI key is not set! Transcription will not be '
                    'available.')
                return False
            else:
                raise ValidationError('OpenAI key is not set!')
        summary_prompt = self.env['connect.settings'].get_param(
            'summary_prompt')
        self.transcribe_recording(openai_key, summary_prompt)

    def transcribe_recording(self, openai_api_key, summary_prompt):
        # Attachment-based variant of the core method: feed Whisper from
        # recording_attachment instead of downloading media_url.
        if self.media_url or not self.recording_attachment:
            return super().transcribe_recording(
                openai_api_key, summary_prompt)
        result = {}
        temp_file_path = None
        try:
            client = self.env['connect.settings'].get_openai_client()
            with NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
                temp_file.write(base64.b64decode(self.recording_attachment))
                temp_file_path = temp_file.name
            with open(temp_file_path, 'rb') as audio_file:
                transcript = client.audio.transcriptions.create(
                    model='whisper-1', file=audio_file,
                    response_format='verbose_json',
                    timestamp_granularities=['segment'])
            segments = ''
            for s in transcript.segments:
                seconds = int(s.start)
                ts = (f"{int(seconds // 3600):02d}:"
                      f"{int((seconds % 3600) // 60):02d}:"
                      f"{int(seconds % 60):02d}")
                segments += '{} {}\n'.format(ts, s.text)
            result['transcript'] = segments
            result.update(
                self.make_summary(client, summary_prompt, result['transcript']))
            result.setdefault('transcription_error', False)
        except Exception as e:
            logger.exception(f'Transcribe error: {e}')
            result['transcription_error'] = str(e)
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except OSError:
                    logger.warning(
                        'Could not remove temp file %s', temp_file_path)
            result['transcription_pending'] = False
            self.write(result)
            self._delete_after_successful_transcription()
