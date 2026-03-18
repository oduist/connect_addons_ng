import base64
import logging

from odoo import http
from odoo.http import request, Response

logger = logging.getLogger(__name__)


class FreeSwitchRecordingController(http.Controller):
    """Controller for receiving recording files from FreeSWITCH.

    FreeSWITCH posts recording files via record_session with an HTTP URL.
    The upload (PUT) may arrive before the CDR webhook creates the channel
    record, so we save the recording with just the UUID (call_sid) and
    link it to the channel later when processing the CDR.
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

            # Skip if recording for this UUID already exists (both legs
            # may attempt to upload the same recording)
            existing = env.sudo().search([('call_sid', '=', uuid)], limit=1)
            if existing:
                logger.info('Recording for UUID %s already exists (id=%s), skipping',
                    uuid, existing.id)
                return Response('OK', status=200)

            # Try to find the channel, but don't fail if not found yet —
            # the CDR handler will link the recording later.
            channel = request.env['connect.channel'].sudo().search(
                [('sid', '=', uuid)], limit=1)

            vals = {
                'call_sid': uuid,
                'status': 'completed',
                'source': 'freeswitch',
                'recording_data': base64.b64encode(file_data),
                'recording_filename': filename,
            }
            if channel:
                vals['call'] = channel.call.id if channel.call else False
                vals['channel'] = channel.id
                vals['partner'] = channel.partner.id if channel.partner else False

            recording = env.sudo().create(vals)

            logger.info('Recording created: id=%s, uuid=%s, channel=%s, size=%d bytes',
                recording.id, uuid, channel.id if channel else 'pending', len(file_data))

        except Exception as e:
            logger.exception('Failed to process recording for %s: %s', uuid, e)
            return Response('Processing error', status=500)

        return Response('OK', status=200)
