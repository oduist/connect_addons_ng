import json
import logging
from werkzeug.exceptions import NotFound
from odoo import http, release
from odoo.api import SUPERUSER_ID

logger = logging.getLogger(__name__)
route_type = "json" if release.version_info[0] < 19.0 else 'jsonrpc'


class ConnectController(http.Controller):

    @http.route('/connect/transcript/<int:rec_id>', methods=['POST'], type=route_type,
                auth='public', csrf=False)
    def upload_transcript(self, rec_id):
        data = json.loads(http.request.httprequest.get_data(as_text=True))
        rec = http.request.env['connect.recording'].sudo().search([
            ('id', '=', rec_id), ('transcription_token', '!=', False),
            ('transcription_token', '=', data['transcription_token'])
        ])
        if not rec:
            raise NotFound()
        rec.with_user(SUPERUSER_ID).update_transcript(data)
        return True

    @http.route('/connect/recording/<int:record_id>', type='http', auth='user')
    def serve_recording(self, record_id):
        recording = http.request.env['connect.recording'].browse(record_id)
        if not recording.exists() or not recording.media_url:
            return http.Response(status=404)
        return self._serve_media(recording.media_url)

    @http.route('/connect/voicemail/<int:record_id>', type='http', auth='user')
    def serve_voicemail(self, record_id):
        call = http.request.env['connect.call'].browse(record_id)
        if not call.exists() or not call.voicemail_url:
            return http.Response(status=404)
        return self._serve_media(call.voicemail_url)

    def _serve_media(self, media_url):
        # Base implementation - integration modules should override with proper auth
        import requests as req
        media_name = '{}.wav'.format(media_url.split('/')[-1])
        response = req.get(media_url)
        if response.status_code == 200:
            res = http.Response(response.content, content_type='audio/wav')
            res.headers['Content-Disposition'] = http.content_disposition(media_name)
            return res
        return http.Response(status=404)

    @http.route('/connect/<string:uid>/', methods=['GET', 'POST'], type='http',
                auth='public', csrf=False)
    def health_check(self, uid):
        instance_uid = http.request.env['connect.settings'].sudo().get_param('instance_uid')
        return "True" if uid == instance_uid else "False"
