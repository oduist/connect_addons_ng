# -*- coding: utf-8 -*-
import datetime
import logging
import os

from odoo import api, models

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)


class Recording(models.Model):
    _inherit = 'connect.recording'

    @api.model
    def on_livekit_egress(self, event):
        """Track an egress lifecycle event in the recording ledger.

        The recording row is created on egress_ended with
        skip_transcription (there is no media yet); the uploader sidecar
        delivers the file to livekit_store_recording_file() which queues
        the transcription. Both orders of arrival are safe.
        """
        info = event.get('egressInfo') or {}
        egress_id = info.get('egressId')
        if not egress_id:
            return False
        etype = event.get('event')
        room_name = info.get('roomName') or ''
        status = (info.get('status') or '').lower().replace('egress_', '')
        files = info.get('fileResults') or []
        file_info = files[0] if files else {}
        filename = os.path.basename(file_info.get('filename') or '')

        rec = self.sudo().search([('sid', '=', egress_id)], limit=1)
        if etype != 'egress_ended':
            if rec:
                rec.with_context(tracking_disable=True).write(
                    {'status': status or etype.replace('egress_', '')})
            return rec.id if rec else False

        if not rec and filename:
            # The uploader delivered the file before the webhook.
            rec = self.sudo().search(
                [('source', '=', 'livekit'),
                 ('recording_filename', '=', filename),
                 ('sid', '=', False)], limit=1)

        call = self.env['connect.call'].sudo().search(
            [('livekit_room_name', '=', room_name)], limit=1)
        vals = {
            'sid': egress_id,
            'source': 'livekit',
            'status': status or 'completed',
            'duration': self._livekit_file_duration(file_info),
            'start_time': self._livekit_file_start(file_info),
        }
        if filename:
            vals['recording_filename'] = filename
        if call:
            vals.update({
                'call': call.id,
                'channel': call.channels[:1].id,
                'partner': call.partner.id,
                'caller_number': call.caller,
                'called_number': call.called,
            })
        if rec:
            rec.with_context(tracking_disable=True).write(vals)
        else:
            rec = self.sudo().with_context(skip_transcription=True).create(
                vals)
        debug(self, 'LiveKit egress {} recorded as {}.'.format(
            egress_id, rec.id))
        return rec.id

    @api.model
    def _livekit_file_duration(self, file_info):
        # FileInfo timestamps are unix nanoseconds.
        try:
            started = int(file_info.get('startedAt') or 0)
            ended = int(file_info.get('endedAt') or 0)
        except (TypeError, ValueError):
            return 0
        if started and ended and ended > started:
            return int((ended - started) / 1e9)
        return 0

    @api.model
    def _livekit_file_start(self, file_info):
        try:
            started = int(file_info.get('startedAt') or 0)
        except (TypeError, ValueError):
            return False
        if not started:
            return False
        # Odoo stores naive UTC datetimes.
        return datetime.datetime.fromtimestamp(
            started / 1e9, tz=datetime.timezone.utc).replace(tzinfo=None)

    @api.model
    def livekit_store_recording_file(self, filename, data_b64):
        """Attach an uploaded egress file to its recording row.

        Called by the uploader sidecar route. Queues the transcription
        once the media is actually present (creating the row with
        transcription_pending before the file arrives would burn the
        single cron attempt on 'Recording is not available yet').
        """
        rec = self.sudo().search(
            [('source', '=', 'livekit'),
             ('recording_filename', '=', filename)],
            order='id desc', limit=1)
        if rec:
            rec.with_context(tracking_disable=True).write(
                {'recording_attachment': data_b64})
        else:
            # Upload arrived before egress_ended: create a stub, the
            # webhook merges the metadata later by filename.
            rec = self.sudo().with_context(skip_transcription=True).create({
                'source': 'livekit',
                'recording_filename': filename,
                'recording_attachment': data_b64,
            })
        if not rec.transcript and self.env[
                'connect.settings'].sudo().get_param('transcript_calls'):
            rec.transcription_pending = True
        return rec.id
