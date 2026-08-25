import base64
import logging
import os
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from tempfile import NamedTemporaryFile
from urllib.parse import quote

import requests
from markupsafe import escape
from odoo import fields, models, api, release, SUPERUSER_ID
from odoo.exceptions import ValidationError

logger = logging.getLogger(__name__)


class Recording(models.Model):
    _name = 'connect.recording'
    _description = 'Recording'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'id'
    _order = 'id desc'

    _TRANSCRIPTION_MODEL = 'whisper-1'
    _TRANSCRIPTION_PRICE_PER_MINUTE = Decimal('0.006')
    _TRANSCRIPTION_PRICE_QUANTUM = Decimal('0.000001')

    call = fields.Many2one('connect.call', ondelete='set null')
    channel = fields.Many2one('connect.channel', ondelete='set null')
    partner = fields.Many2one('res.partner', ondelete='set null')
    sid = fields.Char('SID', readonly=True)
    call_sid = fields.Char(string='Channel SID', readonly=True)
    caller_user = fields.Many2one(related='call.caller_user', store=True, readonly=False)
    called_user = fields.Many2one('res.users', ondelete='set null')
    users = fields.Many2many('res.users', compute='_compute_users', string='Users')
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

    @api.depends(
        'caller_user',
        'called_user',
        'call.caller_user',
        'call.called_users',
        'call.answered_user',
    )
    def _compute_users(self):
        for rec in self:
            users = rec.caller_user | rec.called_user
            if rec.call:
                users |= (
                    rec.call.caller_user
                    | rec.call.called_users
                    | rec.call.answered_user
                )
            rec.users = users

    def _fetch_media_to(self, temp_file):
        """Write this recording's audio into an open binary file object.

        Seam: storage add-ons (connect_s3) override this to read the audio
        from their own backend instead of the provider's URL.
        """
        self.ensure_one()
        if self.recording_attachment:
            # Providers whose recording downloads require API auth
            # store the audio bytes on the record instead of
            # exposing a public media_url (e.g. connect_infobip,
            # Asterisk or LiveKit sidecars).
            temp_file.write(base64.b64decode(self.recording_attachment))
            return
        # Bounded download: media_url points at the provider's
        # recording store; without a timeout a hung endpoint
        # pins the worker.
        response = requests.get(self.media_url, stream=True, timeout=30)
        response.raise_for_status()
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                temp_file.write(chunk)

    def transcribe_recording(self, openai_api_key, summary_prompt):
        result = {}
        temp_file_path = None
        try:
            client = self.env['connect.settings'].get_openai_client()
            # OpenAI infers the audio container from the file extension, so
            # keep the original one when the filename is known.
            suffix = os.path.splitext(self.recording_filename or '')[1] or '.mp3'
            with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                self._fetch_media_to(temp_file)
                temp_file_path = temp_file.name
            with open(temp_file_path, 'rb') as audio_file:
                transcript = client.audio.transcriptions.create(
                    model=self._TRANSCRIPTION_MODEL, file=audio_file,
                    response_format='verbose_json', timestamp_granularities=["segment"])
            result['transcription_price'] = self._get_transcription_price(transcript)
            segments = ''
            for s in transcript.segments:
                seconds = int(s.start)
                ts = f"{int(seconds // 3600):02d}:{int((seconds % 3600) // 60):02d}:{int(seconds % 60):02d}"
                segments += '{} {}\n'.format(ts, s.text)
            result['transcript'] = segments
            result.update(self.make_summary(client, summary_prompt, result['transcript']))
            result.setdefault('transcription_error', False)
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
            result['transcription_pending'] = False
            self.write(result)
            self._delete_after_successful_transcription()

    @api.model
    def _format_transcription_price(self, price):
        if price is None or price is False:
            return False
        try:
            value = Decimal(str(price)).quantize(
                self._TRANSCRIPTION_PRICE_QUANTUM,
                rounding=ROUND_HALF_UP,
            )
        except (InvalidOperation, TypeError, ValueError):
            logger.warning('Invalid transcription price: %r', price)
            return False
        return format(value, 'f').rstrip('0').rstrip('.') or '0'

    @api.model
    def _get_transcription_price(self, transcript):
        usage = getattr(transcript, 'usage', None)
        duration = getattr(usage, 'seconds', None)
        if not isinstance(duration, (int, float, Decimal)):
            duration = getattr(transcript, 'duration', None)
        if not isinstance(duration, (int, float, Decimal)):
            logger.warning('OpenAI transcription response has no duration')
            return False
        price = (
            Decimal(str(duration))
            * self._TRANSCRIPTION_PRICE_PER_MINUTE
            / Decimal('60')
        )
        return self._format_transcription_price(price)

    def make_summary(self, client, summary_prompt, transcript):
        logger.info('Make summary!')
        try:
            settings = self.env['connect.settings']
            model = (
                os.environ.get('OPENAI_COMPLETION_MODEL')
                or settings.get_param('openai_summary_model', 'gpt-5.4-mini')
            )
            max_tokens = int(os.environ.get('OPENAI_COMPLETION_MAX_TOKENS', 4096))
            completion_params = {
                'model': model,
                'messages': [
                    {
                        'role': 'user',
                        'content': summary_prompt
                    },
                    {
                        'role': 'user',
                        'content': transcript,
                    },
                ],
            }
            if model.startswith('gpt-5'):
                completion_params['max_completion_tokens'] = max_tokens
            else:
                completion_params.update({
                    'temperature': float(os.environ.get(
                        'OPENAI_COMPLETION_TEMPERATURE', 0.5)),
                    'max_tokens': max_tokens,
                    'top_p': float(os.environ.get('OPENAI_COMPLETION_TOP_P', 1.0)),
                    'frequency_penalty': float(os.environ.get(
                        'OPENAI_COMPLETION_FREQUENCY_PENALTY', 0.0)),
                    'presence_penalty': float(os.environ.get(
                        'OPENAI_COMPLETION_PRESENCE_PENALTY',
                        os.environ.get('OPENAI_COMPLETION_PRESENSE_PENALTY', 0.0))),
                })
            response = client.chat.completions.create(**completion_params)
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
        call = self.call
        vals = {
            'transcript': data.get('transcript'),
            'transcription_price': self._format_transcription_price(
                data.get('transcription_price')
            ),
            'summary': data.get('summary'),
            'transcription_token': False,
            'transcription_error': data.get('transcription_error'),
            'transcription_pending': False,
        }
        self.with_context(tracking_disable=True).write(vals)
        self._delete_after_successful_transcription()
        if call:
            self.env['connect.settings'].connect_reload_view('connect.call')
        self.env['connect.settings'].connect_reload_view('connect.recording')
        if data.get('notify_uid'):
            self.env['connect.settings'].connect_notify(
                'Transcript updated', notify_uid=data['notify_uid'])

    def _delete_after_successful_transcription(self):
        """Remove processed audio only after its analysis is durable."""
        self.ensure_one()
        if (
            not self.exists()
            or not self.call
            or not self.transcript
            or self.transcription_error
        ):
            return False
        delete_recording = self.env['connect.settings'].sudo().get_param(
            'delete_recording_after_transcription'
        )
        if not delete_recording:
            return False
        self.unlink()
        return True

    def _get_recording_widget(self):
        proxy_recordings = self.env['connect.settings'].sudo().get_param('proxy_recordings')
        for rec in self:
            media_url = rec._get_media_src(proxy_recordings)
            if not media_url:
                rec.recording_widget = ''
                continue
            # media_url may be a raw, webhook-supplied URL when
            # proxy_recordings is off; escape it before it lands in the
            # sanitize=False Html field to prevent stored XSS.
            rec.recording_widget = '<audio id="sound_file" preload="auto" ' \
                'controls="controls"> ' \
                '<source src="{}"/>' \
                '</audio>'.format(escape(media_url))

    def _get_media_src(self, proxy_recordings):
        """Return the URL the player should point at, '' when there is none.

        Seam: storage add-ons (connect_s3) override this to hand out a
        backend-specific URL, e.g. an S3 presigned URL.
        """
        self.ensure_one()
        if self.recording_attachment:
            return self.get_attachment_media_url()
        if self.media_url:
            if proxy_recordings:
                return '/connect/recording/{}'.format(self.id)
            return self.media_url
        return ''

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

    def unlink(self):
        self._sync_analysis_to_call()
        return super().unlink()

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
                if not rec.transcript:
                    rec.get_transcript(fail_silently=True)
            except Exception:
                logger.exception('Cron transcript error for recording %s', rec.id)
            # Clear the flag whether or not it succeeded: transcribe_recording
            # records the transcript or the error, and a single attempt
            # matches the previous inline behaviour while avoiding an
            # unbounded retry loop. The commit is safe here — the cron owns
            # its own transaction, unlike create().
            if rec.exists():
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

    @api.constrains('call', 'transcript', 'summary')
    def _sync_analysis_to_call(self):
        for rec in self.filtered('call'):
            recordings = self.search(
                [('call', '=', rec.call.id)], order='id desc'
            )
            vals = {}
            latest_transcript = recordings.filtered('transcript')[:1]
            latest_summary = recordings.filtered('summary')[:1]
            if rec == latest_transcript:
                vals['transcript'] = rec.transcript
            if rec == latest_summary:
                vals['summary'] = rec.summary
            if vals:
                rec.call.with_user(SUPERUSER_ID).write(vals)
