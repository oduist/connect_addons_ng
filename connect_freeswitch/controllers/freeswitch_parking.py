import logging

from odoo import http
from odoo.http import request, Response

from .token_auth import check_fs_webhook_auth, unauthorized_response

logger = logging.getLogger(__name__)


class FreeSwitchParkingController(http.Controller):
    """Webhook endpoints for FreeSWITCH valet parking events.

    The valet parking dialplan extension (served by freeswitch_xml.py)
    calls this endpoint twice per park cycle:

      - `event=entered` when the channel first enters the lot (via
        `curl ... background`), with UUID and caller info so we can show
        the parked party in the UI before the CDR arrives.
      - `event=released` as the channel's api_hangup_hook, when the
        channel leaves the lot (retrieved, transferred, or hung up).

    Both events are idempotent — replays are safe.
    """

    @http.route(
        '/freeswitch/webhook/parking',
        type='http', auth='none', methods=['GET', 'POST'], csrf=False,
    )
    def parking_webhook(self, **kwargs):
        # The dialplan curl application carries the shared webhook token
        # as a ``token`` query parameter (ADR-025).
        if not check_fs_webhook_auth():
            return unauthorized_response()
        event = kwargs.get('event')
        exten = kwargs.get('slot')
        if not event or not exten:
            return Response('Missing event or slot', status=400)

        Slot = request.env['connect.freeswitch.parking.slot'].sudo()

        try:
            if event == 'entered':
                uuid = kwargs.get('uuid') or ''
                if not uuid:
                    return Response('Missing uuid', status=400)
                Slot.on_parking_entered(
                    exten=exten,
                    uuid=uuid,
                    caller_number=kwargs.get('caller_number', ''),
                    caller_name=kwargs.get('caller_name', ''),
                )
            elif event == 'released':
                Slot.on_parking_released(exten=exten)
            else:
                return Response('Unknown event', status=400)
        except Exception as e:
            logger.exception(
                'Parking webhook failed (event=%s, slot=%s): %s',
                event, exten, e)
            return Response('Processing error', status=500)

        return Response('OK', status=200)
