# -*- coding: utf-8 -*-
import base64
import json
import logging

from odoo import fields, models, api

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)

# Give up on a recording download after this many failed attempts.
MAX_DOWNLOAD_ATTEMPTS = 10


class Recording(models.Model):
    """Infobip recordings are attachment-first (ADR-035): the file download
    requires the App API key, so media_url stays empty and a cron pulls the
    bytes into recording_attachment. Playback, transcription and the proxy
    all ride the attachment path in core."""
    _inherit = 'connect.recording'

    infobip_file_id = fields.Char(readonly=True)
    infobip_download_pending = fields.Boolean(default=False)
    infobip_download_attempts = fields.Integer(default=0)

    @api.model
    def on_infobip_recording(self, event):
        """Handle CALL/DIALOG_RECORDING_FINISHED: create the recording
        rows; the actual file download happens in infobip_fetch_pending."""
        self = self.sudo()
        debug(self, 'On Infobip recording: %s' % json.dumps(event, indent=2))
        properties = event.get('properties') or {}
        recording = (properties.get('recording')
                     or properties.get('callRecording')
                     or properties.get('dialogRecording') or {})
        files = recording.get('files') or []
        if not files and recording.get('fileId'):
            files = [recording]
        call_id = event.get('callId') or recording.get('callId')
        dialog_id = (event.get('dialogId') or properties.get('dialogId')
                     or recording.get('dialogId'))
        Channel = self.env['connect.channel']
        channel = Channel.search([('sid', '=', call_id)], limit=1) if call_id \
            else Channel
        if not channel and dialog_id:
            # Dialog recordings: attach to the parent (first) leg.
            channel = Channel.search(
                [('infobip_dialog_id', '=', dialog_id)],
                order='id asc', limit=1)
        if not channel:
            logger.warning(
                'Infobip recording event without a known channel '
                '(callId=%s, dialogId=%s).', call_id, dialog_id)
            return True
        call = channel.call
        called_user = Channel.search(
            [
                '|',
                ('sid', '=', channel.sid),
                ('parent_channel', '=', channel.id),
                ('called_user', '!=', False),
            ],
            limit=1,
        ).called_user
        for item in files:
            file_id = (item.get('fileId') or item.get('id'))
            if not file_id:
                continue
            if self.search_count([('infobip_file_id', '=', file_id)]):
                continue
            duration = item.get('duration') or recording.get('duration') or 0
            data = {
                'sid': file_id,
                'infobip_file_id': file_id,
                'call_sid': channel.sid,
                'channel': channel.id,
                'call': call.id,
                'partner': call.partner.id,
                'called_user': called_user.id,
                'caller_number': call.caller,
                'called_number': call.called,
                'duration': int(duration),
                'status': 'completed',
                'infobip_download_pending': True,
            }
            # skip_transcription: the core create() must not queue the
            # transcription before the bytes are downloaded; the fetch
            # cron sets transcription_pending itself.
            self.with_context(skip_transcription=True).create(data)
        return True

    @api.model
    def infobip_fetch_pending(self, limit=10):
        """Cron: download pending recording files with the API key into
        recording_attachment, then queue transcription. Runs out of the
        webhook path; each record commits independently."""
        Settings = self.env['connect.settings']
        if not Settings.sudo().get_param('infobip_api_key'):
            return
        pending = self.sudo().search(
            [('infobip_download_pending', '=', True)], limit=limit)
        transcript_calls = Settings.sudo().get_param('transcript_calls')
        for rec in pending:
            try:
                data = Settings.infobip_api_request_raw(
                    'GET', '/calls/1/recordings/files/{}'.format(
                        rec.infobip_file_id))
                rec.write({
                    'recording_attachment': base64.b64encode(data),
                    'recording_filename': '{}.wav'.format(
                        rec.infobip_file_id),
                    'infobip_download_pending': False,
                    'transcription_pending': bool(transcript_calls),
                })
                debug(self, 'Infobip recording {} downloaded ({} bytes).'.format(
                    rec.id, len(data)))
            except Exception as e:
                attempts = rec.infobip_download_attempts + 1
                vals = {'infobip_download_attempts': attempts}
                if attempts >= MAX_DOWNLOAD_ATTEMPTS:
                    vals['infobip_download_pending'] = False
                    logger.error(
                        'Giving up on Infobip recording %s after %s '
                        'attempts: %s', rec.id, attempts, e)
                else:
                    logger.warning(
                        'Infobip recording %s download failed (attempt '
                        '%s): %s', rec.id, attempts, e)
                rec.write(vals)
            # The cron owns its transaction; per-record commits keep one
            # failure from rolling back the batch (core cron pattern).
            self.env.cr.commit()
