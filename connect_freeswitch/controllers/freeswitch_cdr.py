import logging
from xml.etree import ElementTree as ET

from odoo import http
from odoo.http import request, Response

logger = logging.getLogger(__name__)


class FreeSwitchCDRController(http.Controller):
    """Controller for FreeSWITCH CDR (Call Detail Record) webhooks.

    Receives CDR data from mod_xml_cdr after each call ends.
    """

    @http.route(
        '/freeswitch/webhook/cdr',
        type='http', auth='none', methods=['POST'], csrf=False,
    )
    def cdr_webhook(self, **kwargs):
        """Receive CDR from FreeSWITCH mod_xml_cdr.

        mod_xml_cdr sends URL-encoded POST with 'cdr' parameter
        containing XML CDR data.
        """
        cdr_xml = kwargs.get('cdr', '')
        if not cdr_xml:
            # Try raw body (if encode=false in mod_xml_cdr config)
            cdr_xml = request.httprequest.get_data(as_text=True)

        if not cdr_xml:
            logger.warning('Empty CDR received from FreeSWITCH')
            return Response('No CDR data', status=400)

        try:
            cdr_data = self._parse_cdr_xml(cdr_xml)
        except Exception as e:
            logger.exception('Failed to parse FreeSWITCH CDR XML: %s', e)
            return Response('Parse error', status=400)

        try:
            request.env['connect.call'].with_user(
                request.env.ref('connect.user_connect_webhook').id
            ).on_freeswitch_cdr(cdr_data)
        except Exception as e:
            logger.exception('Failed to process FreeSWITCH CDR: %s', e)
            return Response('Processing error', status=500)

        return Response('OK', status=200)

    def _parse_cdr_xml(self, xml_str):
        """Parse FreeSWITCH CDR XML into a dict.

        Extracts relevant fields from the CDR XML structure:
        - Channel UUID
        - Caller/called numbers from caller_profile
        - Duration from billsec or times
        - Direction
        - Hangup cause
        - Odoo channel variables (connect user IDs)
        """
        root = ET.fromstring(xml_str)

        # Channel UUID
        uuid = self._xml_text(root, './/uuid')

        # Caller profile
        caller_profile = root.find('.//caller_profile')
        caller = ''
        called = ''
        direction = 'inbound'

        if caller_profile is not None:
            caller = self._xml_text(caller_profile, 'caller_id_number')
            called = self._xml_text(caller_profile, 'destination_number')
            direction = self._xml_text(caller_profile, 'direction', 'inbound')

        # Hangup cause
        hangup_cause = self._xml_text(root, './/hangup_cause', 'NORMAL_CLEARING')

        # Duration - prefer billsec, fallback to calculation from times
        duration = 0
        billsec = self._xml_text(root, './/billsec')
        if billsec:
            duration = int(billsec)
        else:
            times = root.find('.//times')
            if times is not None:
                answered = self._xml_text(times, 'answered_time', '0')
                hangup = self._xml_text(times, 'hangup_time', '0')
                if answered != '0' and hangup != '0':
                    # Times are in microseconds
                    duration = (int(hangup) - int(answered)) // 1000000

        # Channel variables (set by our XML directory handler)
        variables = root.find('.//variables')
        caller_pbx_user_id = None
        called_pbx_user_id = None
        other_leg_uuid = None

        if variables is not None:
            # Use effective_caller_id_number (set by Odoo directory) if
            # caller_id_number is a SIP username rather than a number
            effective_caller = self._xml_text(
                variables, 'effective_caller_id_number')
            if effective_caller and not caller.isdigit():
                caller = effective_caller

            odoo_user = self._xml_text(variables, 'odoo_connect_user_id')
            if odoo_user:
                # The user who owns this channel leg
                if direction == 'inbound':
                    called_pbx_user_id = int(odoo_user)
                else:
                    caller_pbx_user_id = int(odoo_user)

            other_leg_uuid = self._xml_text(
                variables, 'Other-Leg-Unique-ID')

        return {
            'uuid': uuid,
            'caller': caller,
            'called': called,
            'direction': direction,
            'hangup_cause': hangup_cause,
            'duration': duration,
            'caller_pbx_user_id': caller_pbx_user_id,
            'called_pbx_user_id': called_pbx_user_id,
            'other_leg_uuid': other_leg_uuid,
        }

    @staticmethod
    def _xml_text(element, path, default=''):
        """Safely get text from an XML element."""
        el = element.find(path)
        if el is not None and el.text:
            return el.text.strip()
        return default
