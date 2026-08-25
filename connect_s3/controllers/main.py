# -*- coding: utf-8 -*-
import logging

from odoo import http

from odoo.addons.connect.controllers.main import ConnectController
from odoo.addons.connect_s3.models import s3_utils

logger = logging.getLogger(__name__)


class ConnectS3Controller(ConnectController):
    """Serve recordings that live in the customer's S3 bucket.

    Covers both core routes, /connect/recording/<id> and
    /connect/voicemail/<id>, since both funnel through _serve_media.
    """

    def _serve_media(self, media_url):
        settings = http.request.env['connect.settings'].sudo()
        bucket = settings.get_param('aws_s3_bucket_name')
        if not (settings.get_param('s3_recordings_enabled')
                and s3_utils.is_s3_media_url(media_url, bucket)):
            # Pre-switch recordings still live at the provider; core fetches
            # them with the credentials connect.settings.get_media_auth()
            # supplies (ADR-060).
            return super()._serve_media(media_url)
        key = s3_utils.parse_s3_key(media_url, bucket)
        s3 = settings._get_s3_client()
        try:
            obj = s3.get_object(Bucket=bucket, Key=key)
        except s3.exceptions.NoSuchKey:
            # Safety net for a lifecycle deletion that recording_expired did
            # not predict, e.g. the retention window was shortened later.
            logger.info('S3 object gone for key %s', key)
            return http.Response(status=410)
        data = obj['Body'].read()
        res = http.Response(
            data, content_type=obj.get('ContentType') or 'audio/mpeg'
        )
        res.headers['Content-Disposition'] = http.content_disposition(
            key.split('/')[-1]
        )
        return res
