import base64
import json
import logging
import os
import requests
from urllib.parse import quote
from markupsafe import escape
from tempfile import NamedTemporaryFile
from odoo import fields, models, api, release, SUPERUSER_ID
from odoo.exceptions import ValidationError
from .settings import format_connect_response, debug

logger = logging.getLogger(__name__)


class Recording(models.Model):
    _name = 'connect.recording'
    _description = 'Recording'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'id'
    _order = 'id desc'

    call = fields.Many2one('connect.call', ondelete='set null')
    channel = fields.Many2one('connect.channel', ondelete='set null')
    partner = fields.Many2one('res.partner', ondelete='set null')
    sid = fields.Char('SID', readonly=True)
    call_sid = fields.Char(string='Channel SID', readonly=True)
    caller_user = fields.Many2one(related='call.caller_user', store=True, readonly=False)
    called_user = fields.Many2one('res.users', ondelete='set null')
    caller_number = fields.Char()
    called_number = fields.Char()
    media_url = fields.Char()
    recording_filename = fields.Char(readonly=True)
    recording_attachment = fields.Binary(attachment=True, readonly=True)
    price = fields.Char()
    price_unit = fields.Char()
    source = fields.Char()
    duration = fields.Integer()
    duration_human = fields.Char(compute='_get_duration_human')
    start_time = fields.Datetime()
    status = fields.Char()
    if release.version_info[0] >= 17.0:
        recording_widget = fields.Html(compute='_get_recording_widget', string='Recording', sanitize=False)
    else:
        recording_widget = fields.Char(compute='_get_recording_widget', string='Recording')
    transcript = fields.Text()
    transcription_token = fields.Char()
    transcription_error = fields.Char()
    # Work-queue flag for the transcription cron. Set on create() when
    # transcript_calls is enabled; the cron picks these up out of the
    # request path (see _cron_transcribe_recordings).
    transcription_pending = fields.Boolean(default=False, copy=False)
    transcription_price = fields.Char()
    summary = fields.Html()
    list_view_summary = fields.Html(compute='_get_list_view_summary')

    def transcribe_recording(self, openai_api_key, summary_prompt):
        result = {}
        temp_file_path = None
        try:
            client = self.env['connect.settings'].get_openai_client()
            # OpenAI infers the audio container from the file extension, so
            # keep the original one when the filename is known.
            suffix = os.path.splitext(self.recording_filename or '')[1] or '.mp3'
            with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                if self.recording_attachment:
                    # Providers whose recording downloads require API auth
                    # store the audio bytes on the record instead of
                    # exposing a public media_url (e.g. connect_infobip,
                    # Asterisk or LiveKit sidecars).
                    temp_file.write(base64.b64decode(self.recording_attachment))
                else:
                    # Bounded download: media_url points at the provider's
                    # recording store; without a timeout a hung endpoint
                    # pins the worker.
                    response = requests.get(self.media_url, stream=True, timeout=30)
                    response.raise_for_status()
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            temp_file.write(chunk)
                temp_file_path = temp_file.name
            with open(temp_file_path, 'rb') as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1", file=audio_file,
                    response_format='verbose_json', timestamp_granularities=["segment"])
            segments = ''
            for s in transcript.segments:
                seconds = int(s.start)
                ts = f"{int(seconds // 3600):02d}:{int((seconds % 3600) // 60):02d}:{int(seconds % 60):02d}"
                segments += '{} {}\n'.format(ts, s.text)
            result['transcript'] = segments
            result.update(self.make_summary(client, summary_prompt, result['transcript']))
            result['transcription_error'] = False
        except Exception as e:
            logger.exception(f'Transcribe error: {e}')
            result['transcription_error'] = str(e)
        finally:
            # NamedTemporaryFile(delete=False) is not auto-removed; drop the
            # downloaded audio so /tmp does not grow without bound.
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except OSError:
                    logger.warning('Could not remove temp file %s', temp_file_path)
            self.write(result)

    def make_summary(self, client, summary_prompt, transcript):
        logger.info('Make summary!')
        try:
            response = client.chat.completions.create(
                model=os.environ.get('OPENAI_COMPLETION_MODEL', 'gpt-4o'),
                messages=[
                    {
                        'role': 'user',
                        'content': summary_prompt
                    },
                    {
                        'role': 'user',
                        'content': transcript,
                    },
                ],
                temperature=float(os.environ.get('OPENAI_COMPLETION_TEMPERATURE', 0.5)),
                max_tokens=int(os.environ.get('OPENAI_COMPLETION_MAX_TOKENS', 4096)),
                top_p=float(os.environ.get('OPENAI_COMPLETION_TOP_P', 1.0)),
                frequency_penalty=float(os.environ.get('OPENAI_COMPLETION_FREQUENCY_PENALTY', 0.0)),
                presence_penalty=float(os.environ.get(
                    'OPENAI_COMPLETION_PRESENCE_PENALTY',
                    os.environ.get('OPENAI_COMPLETION_PRESENSE_PENALTY', 0.0))),
            )
            logger.info('%s', response.usage)
            return {'summary': response.choices[0].message.content.strip('\n\n')}
        except Exception as e:
            logger.exception(f'Summary error: {e}')
            return {'transcription_error': str(e)}

    def get_transcript(self, fail_silently=False):
        self.ensure_one()
        openai_key = self.env['connect.settings'].sudo().get_param('openai_api_key')
        if not openai_key:
            if fail_silently:
                logger.warning('OpenAI key is not set! Transcription will not be available.')
                return False
            else:
                raise ValidationError('OpenAI key is not set!')
        summary_prompt = self.env['connect.settings'].get_param('summary_prompt')
        if not self.media_url and not self.recording_attachment:
            raise ValidationError('Recording is not available yet!')
        self.transcribe_recording(openai_key, summary_prompt)

    def update_transcript(self, data):
        self.ensure_one()
        transcription_price = data.get('transcription_price')
        if transcription_price:
            transcription_price = round(transcription_price, 2)
        vals = {
            'transcript': data.get('transcript'),
            'transcription_price': str(transcription_price),
            'summary': data.get('summary'),
            'transcription_token': False,
            'transcription_error': data.get('transcription_error')
        }
        self.with_context(tracking_disable=True).write(vals)
        if self.call:
            self.call.summary = data.get('summary')
            self.env['connect.settings'].connect_reload_view('connect.call')
        self.env['connect.settings'].connect_reload_view('connect.recording')
        if data.get('notify_uid'):
            self.env['connect.settings'].connect_notify(
                'Transcript updated', notify_uid=data['notify_uid'])

    def _get_recording_widget(self):
        proxy_recordings = self.env['connect.settings'].sudo().get_param('proxy_recordings')
        for rec in self:
            if rec.recording_attachment:
                media_url = rec.get_attachment_media_url()
            elif rec.media_url:
                if proxy_recordings:
                    media_url = '/connect/recording/{}'.format(rec.id)
                else:
                    media_url = rec.media_url
            else:
                rec.recording_widget = ''
                continue
            # media_url may be a raw, webhook-supplied URL when
            # proxy_recordings is off; escape it before it lands in the
            # sanitize=False Html field to prevent stored XSS.
            rec.recording_widget = '<audio id="sound_file" preload="auto" ' \
                'controls="controls"> ' \
                '<source src="{}"/>' \
                '</audio>'.format(escape(media_url))

    def get_attachment_media_url(self):
        self.ensure_one()
        if not self.recording_attachment:
            return ''
        filename = quote(self.recording_filename or 'recording.wav')
        return (
            '/web/content?model=connect.recording'
            '&id={}&field=recording_attachment'
            '&filename_field=recording_filename'
            '&filename={}&download=True'.format(self.id, filename))

    def _get_list_view_summary(self):
        for rec in self:
            rec.list_view_summary = rec.summary

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('skip_transcription'):
            return super().create(vals_list)
        transcript_calls = self.env['connect.settings'].sudo().get_param('transcript_calls')
        recs = super(Recording, self.with_context(
            mail_create_nosubscribe=True, mail_create_nolog=True)).create(vals_list)
        if transcript_calls:
            # Defer transcription to _cron_transcribe_recordings. Running
            # the Whisper + GPT round trip inline blocked the provider
            # webhook that created the recording (timeout -> retry ->
            # duplicate processing) and was only survivable via a
            # mid-create cr.commit() that broke the caller transaction's
            # atomicity. The flag is the cron's work queue instead.
            recs.filtered(lambda r: not r.transcript).transcription_pending = True
        return recs

    @api.model
    def _cron_transcribe_recordings(self, limit=20):
        """Transcribe recordings queued by create() (transcription_pending).

        Runs out of the request path so a slow OpenAI round trip never
        blocks a provider webhook. Each recording is committed
        independently so one failure does not roll back the batch.
        """
        pending = self.search([('transcription_pending', '=', True)], limit=limit)
        for rec in pending:
            try:
                rec.get_transcript(fail_silently=True)
            except Exception:
                logger.exception('Cron transcript error for recording %s', rec.id)
            # Clear the flag whether or not it succeeded: transcribe_recording
            # records the transcript or the error, and a single attempt
            # matches the previous inline behaviour while avoiding an
            # unbounded retry loop. The commit is safe here — the cron owns
            # its own transaction, unlike create().
            rec.transcription_pending = False
            self.env.cr.commit()

    @api.depends('duration')
    def _get_duration_human(self):
        for record in self:
            if record.duration is not None:
                minutes = record.duration // 60
                seconds = record.duration % 60
                record.duration_human = '{:02}:{:02}'.format(minutes, seconds)
            else:
                record.duration_human = "00:00"

    @api.constrains('summary')
    def _sync_summary(self):
        if self.call:
            self.with_user(SUPERUSER_ID).call.summary = self.summary
