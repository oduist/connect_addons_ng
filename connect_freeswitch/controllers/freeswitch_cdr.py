import logging
import re
import urllib.parse
from xml.etree import ElementTree as ET

from odoo import http
from odoo.http import request, Response

from .token_auth import check_fs_webhook_auth, unauthorized_response

logger = logging.getLogger(__name__)


class FreeSwitchCDRController(http.Controller):
    """Controller for FreeSWITCH CDR (Call Detail Record) webhooks.

    Receives CDR data from mod_xml_cdr after each call ends.
    """

    @http.route(
        '/freeswitch/webhook/cdr',
        type='http', auth='public', methods=['POST'], csrf=False,
    )
    def cdr_webhook(self, **kwargs):
        """Receive CDR from FreeSWITCH mod_xml_cdr.

        mod_xml_cdr sends URL-encoded POST with 'cdr' parameter
        containing XML CDR data. Authenticated with the shared webhook
        token via mod_xml_cdr's cred/auth-scheme params (ADR-025).
        """
        if not check_fs_webhook_auth():
            return unauthorized_response()
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
        # FreeSWITCH CDR XML may contain element names with colons
        # (e.g. SIP headers like sip:to-host) which are invalid XML
        # namespace prefixes. Replace colons in tag names to avoid parse errors.
        xml_str = re.sub(
            r'<(/?)([a-zA-Z_][\w.-]*):([a-zA-Z_][\w.-]*)',
            r'<\1\2_\3', xml_str)
        root = ET.fromstring(xml_str)

        # Channel UUID
        uuid = self._xml_text(root, './/uuid')

        # Caller profile
        caller_profile = root.find('.//caller_profile')
        caller = ''
        called = ''

        if caller_profile is not None:
            caller = self._xml_text(caller_profile, 'caller_id_number')
            called = self._xml_text(caller_profile, 'destination_number')

        # FreeSWITCH stores the channel's direction in <channel_data>
        # at the top of the CDR — `inbound` for the originator (UA → FS)
        # leg, `outbound` for the gateway (FS → PSTN) leg. The previous
        # XPath (`caller_profile/direction`) never matched in any FS
        # version, so every CDR was parsed as `inbound`.
        channel_data = root.find('./channel_data')
        if channel_data is not None:
            direction = self._xml_text(channel_data, 'direction', 'inbound')
        else:
            direction = 'inbound'

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
        chain_id = None
        odoo_number_id = None
        odoo_call_direction = None

        if variables is not None:
            # Click-to-call originates `user/<login>@<domain>` and the
            # user directory rewrites the channel's effective caller-id
            # back to the extension, silently overriding any globals
            # `connect.call.originate` tried to set. The originate path
            # therefore stashes the intended caller-id on the custom
            # `odoo_caller_id_number` variable — prefer that. UA-
            # originated calls don't set it; they get the right value
            # from `effective_caller_id_number` (rewritten by the
            # outgoing-route dialplan, ADR-021).
            #
            # mod_xml_cdr URL-encodes channel variable values inside
            # <variables> (`+` → `%2B`, `@` → `%40`), so unquote first.
            odoo_caller_id = urllib.parse.unquote(self._xml_text(
                variables, 'odoo_caller_id_number'))
            effective_caller = urllib.parse.unquote(self._xml_text(
                variables, 'effective_caller_id_number'))
            if odoo_caller_id:
                caller = odoo_caller_id
            elif effective_caller:
                caller = effective_caller

            # Click-to-call originates `user/<login>@<domain>`, so the
            # A-leg's caller_profile.destination_number is the resolved
            # user URI rather than the dialled number. The originate
            # path stashes the real destination as a channel variable;
            # use it when present.
            odoo_destination = urllib.parse.unquote(self._xml_text(
                variables, 'odoo_destination_number'))
            if odoo_destination:
                called = odoo_destination

            # B-leg discriminator: mod_xml_cdr always sets `originator`
            # (and `originating_leg_uuid`) on the originatee side; the
            # originator does not have them. `bridge_uuid` / `signal_bond`
            # are present on both legs and are NOT reliable for A/B
            # detection.
            originator_uuid = (
                self._xml_text(variables, 'originator')
                or self._xml_text(variables, 'originating_leg_uuid')
            )

            # `other_leg_uuid` drives parent-channel linking in
            # `connect.channel.process_channel_event`. We populate it
            # only on the B-leg (= originatee) so the A-leg has no
            # parent. The A-leg picks up its B-leg via the reverse-orphan
            # check in `connect.call.on_freeswitch_cdr` once the B-leg
            # CDR arrives.
            other_leg_uuid = (
                self._xml_text(variables, 'odoo_parent_uuid')
                or self._xml_text(variables, 'Other-Leg-Unique-ID')
                or originator_uuid
            )
            chain_id = self._xml_text(variables, 'odoo_chain_id')

            odoo_user = self._xml_text(variables, 'odoo_connect_user_id')
            odoo_called_user = self._xml_text(
                variables, 'odoo_called_user_id')
            if originator_uuid:
                # B-leg: odoo_connect_user_id (if present) identifies the
                # called connect.user.
                if odoo_user:
                    called_pbx_user_id = int(odoo_user)
            else:
                # A-leg: odoo_connect_user_id is the caller,
                # odoo_called_user_id is the called user.
                if odoo_user:
                    caller_pbx_user_id = int(odoo_user)
                if odoo_called_user:
                    called_pbx_user_id = int(odoo_called_user)

            odoo_number_id = self._xml_text(variables, 'odoo_number_id')

            # The dialplan stamps the business-logic call direction on the
            # channel (`odoo_call_direction`: 'inbound' on inbound DID
            # routes, 'outgoing' on outgoing routes). It is a plain word,
            # so no URL-decoding is needed. Prefer it downstream over
            # FreeSWITCH's native per-leg direction, which marks the UA /
            # originate leg of an outbound call as 'inbound' and mislabels
            # such calls as incoming (issue #43).
            odoo_call_direction = self._xml_text(
                variables, 'odoo_call_direction') or None

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
            'chain_id': chain_id,
            'odoo_call_direction': odoo_call_direction,
            'odoo_number_id': int(odoo_number_id) if odoo_number_id else None,
        }

    @staticmethod
    def _xml_text(element, path, default=''):
        """Safely get text from an XML element."""
        el = element.find(path)
        if el is not None and el.text:
            return el.text.strip()
        return default
