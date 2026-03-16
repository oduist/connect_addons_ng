import base64
import logging

from odoo import http
from odoo.http import request, Response

logger = logging.getLogger(__name__)


class FreeSwitchRecordingController(http.Controller):
    """Controller for receiving recording files from FreeSWITCH.

    FreeSWITCH posts recording files via record_session with an HTTP URL.
    """

    @http.route(
        '/freeswitch/webhook/recording/<string:filename>',
        type='http', auth='none', methods=['PUT', 'POST'], csrf=False,
    )
    def recording_webhook(self, filename, **kwargs):
        """Receive a recording file from FreeSWITCH.

        The filename is expected to be <uuid>.wav where uuid is
        the FreeSWITCH channel UUID (used as channel SID in Odoo).
        """
        # Extract UUID from filename (strip extension)
        uuid = filename.rsplit('.', 1)[0] if '.' in filename else filename

        if not uuid:
            logger.warning('Recording webhook: no UUID in filename %s', filename)
            return Response('No UUID', status=400)

        # Get the raw file data
        file_data = request.httprequest.get_data()
        if not file_data:
            logger.warning('Recording webhook: empty file data for %s', uuid)
            return Response('No file data', status=400)

        try:
            env = request.env['connect.recording'].with_user(
                request.env.ref('connect.user_connect_webhook').id
            )

            # Find the channel by UUID (sid)
            channel = request.env['connect.channel'].sudo().search(
                [('sid', '=', uuid)], limit=1)

            if not channel:
                logger.warning('Recording webhook: channel not found for UUID %s', uuid)
                return Response('Channel not found', status=404)

            # Create recording with the file as an attachment
            recording = env.sudo().create({
                'call': channel.call.id if channel.call else False,
                'channel': channel.id,
                'call_sid': uuid,
                'partner': channel.partner.id if channel.partner else False,
                'status': 'completed',
                'source': 'freeswitch',
            })

            # Store the recording file as an attachment
            attachment = request.env['ir.attachment'].sudo().create({
                'name': filename,
                'type': 'binary',
                'datas': base64.b64encode(file_data),
                'res_model': 'connect.recording',
                'res_id': recording.id,
                'mimetype': 'audio/wav',
            })

            # Set media_url to the attachment download URL
            recording.sudo().write({
                'media_url': '/web/content/{}?download=true'.format(attachment.id),
            })

            logger.info('Recording created: id=%s, channel=%s, size=%d bytes',
                recording.id, uuid, len(file_data))

        except Exception as e:
            logger.exception('Failed to process recording for %s: %s', uuid, e)
            return Response('Processing error', status=500)

        return Response('OK', status=200)
