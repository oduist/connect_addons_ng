# -*- coding: utf-8 -*-
import logging

from odoo import fields, models

from . import s3_utils

logger = logging.getLogger(__name__)

# How long a presigned playback URL stays valid. One hour is long enough for a
# page to sit open and short enough that a leaked URL goes stale quickly.
PRESIGNED_URL_TTL = 3600


class Recording(models.Model):
    _inherit = 'connect.recording'

    recording_expired = fields.Boolean(compute='_compute_recording_expired')

    def _compute_recording_expired(self):
        days = self.env['connect.settings'].sudo().get_param('s3_retention_days')
        now = fields.Datetime.now()
        for rec in self:
            rec.recording_expired = s3_utils.is_recording_expired(
                rec.start_time, days, now
            )

    def _s3_object(self):
        """Return (bucket, key) when this recording lives in our bucket, else ().

        Recordings created before Twilio's external storage was switched on
        still point at api.twilio.com and must keep using the inherited path.
        """
        self.ensure_one()
        if self.recording_attachment:
            return ()
        settings = self.env['connect.settings'].sudo()
        if not settings.get_param('s3_recordings_enabled'):
            return ()
        bucket = settings.get_param('aws_s3_bucket_name')
        if not s3_utils.is_s3_media_url(self.media_url, bucket):
            return ()
        return bucket, s3_utils.parse_s3_key(self.media_url, bucket)

    def _fetch_media_to(self, temp_file):
        target = self._s3_object()
        if not target:
            return super()._fetch_media_to(temp_file)
        bucket, key = target
        self.env['connect.settings'].sudo()._get_s3_client().download_fileobj(
            bucket, key, temp_file
        )

    def _get_media_src(self, proxy_recordings):
        # When proxying, the player hits /connect/recording/<id> and the
        # controller does the S3 read — no presigned URL needed.
        if proxy_recordings:
            return super()._get_media_src(proxy_recordings)
        target = self._s3_object()
        if not target:
            return super()._get_media_src(proxy_recordings)
        bucket, key = target
        return self.env['connect.settings'].sudo()._get_s3_client().generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': key},
            ExpiresIn=PRESIGNED_URL_TTL,
        )

    def _get_recording_widget(self):
        super()._get_recording_widget()
        # The audio is gone once the lifecycle rule fires, but the row keeps
        # its transcript and summary — say so instead of showing a dead player.
        for rec in self:
            if rec.recording_expired:
                rec.recording_widget = '<i>Recording expired</i>'
