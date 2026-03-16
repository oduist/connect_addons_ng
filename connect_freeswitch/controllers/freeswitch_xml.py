# -*- coding: utf-8 -*-
import logging
import re
from xml.etree import ElementTree as ET
from xml.dom import minidom

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


def pretty_xml(xml_str):
    """Pretty-print XML string with proper indentation."""
    try:
        dom = minidom.parseString(xml_str)
        pretty = dom.toprettyxml(indent='  ')
        # Remove XML declaration and extra blank lines
        return '\n'.join(line for line in pretty.split('\n') if line.strip() and not line.startswith('<?xml'))
    except Exception as e:
        _logger.warning("Failed to pretty-print XML: %s", e)
        return xml_str


class FreeSwitchXMLController(http.Controller):
    """
    Controller for FreeSWITCH XML configuration requests.
    FreeSWITCH sends POST requests with section parameter to fetch configuration.
    """

    @http.route('/freeswitch/xml', type='http', auth='none', methods=['POST'], csrf=False)
    def freeswitch_xml(self, **kwargs):
        """
        Main endpoint for FreeSWITCH XML curl requests.

        FreeSWITCH sends these POST parameters:
        - section: configuration, directory, dialplan
        - tag_name: for directory requests
        - key_name, key_value: for specific lookups
        - user, domain: for user authentication
        - action: for specific actions (e.g., sip_auth)
        """
        section = kwargs.get('section', '')
        _logger.info("FreeSWITCH XML request: section=%s, params=%s", section, kwargs)

        if section == 'directory':
            return self._handle_directory(kwargs)
        elif section == 'dialplan':
            return self._handle_dialplan(kwargs)
        elif section == 'configuration':
            return self._handle_configuration(kwargs)
        else:
            return self._not_found()

    def _handle_directory(self, params):
        """Handle directory section requests (user authentication and lookup)."""
        action = params.get('action', '')
        # FreeSWITCH sends user ID in different params depending on request type
        user = params.get('user') or params.get('key_value', '')
        domain = params.get('domain') or params.get('sip_auth_realm', '')

        _logger.debug("Directory request: action=%s, user=%s, domain=%s", action, user, domain)

        # User lookup/authentication - user is enough, domain can be empty
        if user:
            return self._get_user_xml(user, domain, params)

        # Full directory request
        if params.get('purpose') == 'gateways':
            return self._not_found()

        return self._get_full_directory(domain)

    def _get_user_xml(self, user, domain, params):
        """Generate XML for a specific user."""
        Endpoint = request.env['connect.endpoint'].sudo()
        ConnectUser = request.env['connect.user'].sudo()

        # 1. Search by auth_user (for registration/login)
        endpoint = Endpoint.search([
            ('auth_user', '=', user),
            ('active', '=', True),
            '|', ('sip_enabled', '=', True), ('webrtc_enabled', '=', True)
        ], limit=1)

        # 2. If not found, search by exten_number (for incoming call/bridge)
        if not endpoint:
            connect_user = ConnectUser.search([
                ('exten_number', '=', user),
                ('active', '=', True)
            ], limit=1)
            if connect_user:
                # Get the first active endpoint for this user
                endpoint = Endpoint.search([
                    ('connect_user_id', '=', connect_user.id),
                    ('active', '=', True),
                    '|', ('sip_enabled', '=', True), ('webrtc_enabled', '=', True)
                ], limit=1)

        if not endpoint:
            _logger.debug("User not found in Odoo: %s", user)
            return self._not_found()

        connect_user = endpoint.connect_user_id

        # CRITICAL: FS expects the XML ID to match the requested 'user'
        # If '1000' was requested, return '1000' even if the endpoint is 'admin'
        xml_user_id = user

        actual_domain = endpoint.domain or domain or params.get('sip_auth_realm') or '80.246.208.201'

        root = ET.Element('document', type='freeswitch/xml')
        section = ET.SubElement(root, 'section', name='directory')
        domain_el = ET.SubElement(section, 'domain', name=actual_domain)

        # User ID is dynamic
        user_el = ET.SubElement(domain_el, 'user', id=xml_user_id)

        # Params
        user_params = ET.SubElement(user_el, 'params')
        ET.SubElement(user_params, 'param', name='password', value=endpoint.auth_password or '')
        ET.SubElement(user_params, 'param', name='vm-password', value=endpoint.auth_password or '')

        # Build dial-string so that bridge(user/1000) works
        # This tells FS to ring both SIP and Verto endpoints for this user
        dial_parts = []
        if endpoint.sip_enabled:
            dial_parts.append(f"${{sofia_contact(*/{xml_user_id}@{actual_domain})}}")
        if endpoint.webrtc_enabled:
            dial_parts.append(f"${{verto_contact({xml_user_id}@{actual_domain})}}")

        dial_string = ",".join(dial_parts)
        ET.SubElement(user_params, 'param', name='dial-string', value=dial_string)

        # Verto-specific
        ET.SubElement(user_params, 'param', name='verto-context', value='default')
        ET.SubElement(user_params, 'param', name='verto-dialplan', value='XML')
        ET.SubElement(user_params, 'param', name='jsonrpc-allowed-methods', value='verto')
        ET.SubElement(user_params, 'param', name='jsonrpc-allowed-event-channels', value='demo,presence,conference')

        # Variables
        variables = ET.SubElement(user_el, 'variables')
        ET.SubElement(variables, 'variable', name='user_context', value='default')

        # Caller ID from the associated connect user
        cid_name = connect_user.name or endpoint.auth_user
        cid_num = connect_user.exten_number or endpoint.auth_user

        ET.SubElement(variables, 'variable', name='effective_caller_id_name', value=cid_name)
        ET.SubElement(variables, 'variable', name='effective_caller_id_number', value=cid_num)
        ET.SubElement(variables, 'variable', name='outbound_caller_id_name', value=cid_name)
        ET.SubElement(variables, 'variable', name='outbound_caller_id_number', value=cid_num)

        # Odoo Tracking
        ET.SubElement(variables, 'variable', name='odoo_connect_user_id', value=str(connect_user.id))
        ET.SubElement(variables, 'variable', name='odoo_endpoint_id', value=str(endpoint.id))
        if connect_user.user:
            ET.SubElement(variables, 'variable', name='odoo_user_id', value=str(connect_user.user.id))

        return self._xml_response(root)

    def _get_full_directory(self, domain):
        """Generate full directory XML with all users."""
        Endpoint = request.env['connect.endpoint'].sudo()

        endpoints = Endpoint.search([
            ('active', '=', True),
            ('auth_user', '!=', False),
            ('auth_password', '!=', False),
            '|', ('sip_enabled', '=', True), ('webrtc_enabled', '=', True)
        ])

        if not endpoints:
            return self._not_found()

        # Use endpoint domain if available, fallback to request domain or IP
        actual_domain = domain or '80.246.208.201'
        # Note: Full directory uses request domain; individual endpoints use their own domain

        root = ET.Element('document', type='freeswitch/xml')
        section = ET.SubElement(root, 'section', name='directory')
        domain_el = ET.SubElement(section, 'domain', name=actual_domain)

        # Users directly inside domain (flat structure for xml_curl compatibility)
        for endpoint in endpoints:
            connect_user = endpoint.connect_user_id

            user_el = ET.SubElement(domain_el, 'user', id=endpoint.auth_user)

            # Params with Verto support
            user_params = ET.SubElement(user_el, 'params')
            ET.SubElement(user_params, 'param', name='password', value=endpoint.auth_password)
            ET.SubElement(user_params, 'param', name='vm-password', value=endpoint.auth_password)
            ET.SubElement(user_params, 'param', name='verto-context', value='default')
            ET.SubElement(user_params, 'param', name='verto-dialplan', value='XML')
            ET.SubElement(user_params, 'param', name='jsonrpc-allowed-methods', value='verto')
            ET.SubElement(user_params, 'param', name='jsonrpc-allowed-event-channels', value='demo,presence,conference')

            # Variables
            variables = ET.SubElement(user_el, 'variables')
            ET.SubElement(variables, 'variable', name='user_context', value='default')
            ET.SubElement(variables, 'variable', name='effective_caller_id_name', value=connect_user.name or endpoint.auth_user)
            ET.SubElement(variables, 'variable', name='effective_caller_id_number', value=connect_user.exten_number or endpoint.auth_user)
            ET.SubElement(variables, 'variable', name='outbound_caller_id_name', value=connect_user.name or endpoint.auth_user)
            ET.SubElement(variables, 'variable', name='outbound_caller_id_number', value=connect_user.exten_number or endpoint.auth_user)
            ET.SubElement(variables, 'variable', name='odoo_connect_user_id', value=str(connect_user.id))
            ET.SubElement(variables, 'variable', name='odoo_endpoint_id', value=str(endpoint.id))
            if connect_user.user:
                ET.SubElement(variables, 'variable', name='odoo_user_id', value=str(connect_user.user.id))

        return self._xml_response(root)

    def _handle_dialplan(self, params):
        """Handle dialplan section requests.

        Routing logic:
        - public context: inbound DID routing via connect.number
        - default context: extension lookup, then outgoing routes, then fallback
        """
        context = params.get('Caller-Context', params.get('Hunt-Context', 'default'))
        destination = params.get('Caller-Destination-Number', '')

        _logger.info("Dialplan request: context=%s, destination=%s", context, destination)

        root = ET.Element('document', type='freeswitch/xml')
        section = ET.SubElement(root, 'section', name='dialplan')
        context_el = ET.SubElement(section, 'context', name=context)

        if context == 'public':
            # Inbound DID routing
            self._route_inbound(context_el, destination, params)
        else:
            # Internal routing: extensions, outgoing, system
            self._route_internal(context_el, destination, params)

        return self._xml_response(root)

    def _route_inbound(self, context_el, destination, params):
        """Route inbound calls from PSTN trunks via connect.number."""
        Number = request.env['connect.number'].sudo()

        # Try exact match on phone number
        number = Number.search([
            ('phone_number', '=', destination),
            ('is_ignored', '=', False),
        ], limit=1)

        # Try with + prefix if not found
        if not number and not destination.startswith('+'):
            number = Number.search([
                ('phone_number', '=', '+' + destination),
                ('is_ignored', '=', False),
            ], limit=1)

        if number:
            number.generate_dialplan(context_el, params)
        else:
            _logger.warning("No DID configured for inbound number: %s", destination)
            ext = ET.SubElement(context_el, 'extension', name='unmatched_inbound')
            condition = ET.SubElement(ext, 'condition',
                field='destination_number', expression='.*')
            ET.SubElement(condition, 'action', application='respond', data='404')

    def _route_internal(self, context_el, destination, params):
        """Route internal calls: extensions, outgoing routes, system extensions."""
        Exten = request.env['connect.exten'].sudo()

        # System extensions
        self._add_system_extensions(context_el)

        # Try exact extension match
        exten = Exten.search([('number', '=', destination)], limit=1)
        if exten:
            exten.generate_dialplan(context_el, params)
            return

        # Try regex pattern match against all extensions
        all_extens = Exten.search([])
        for ext in all_extens:
            try:
                if re.match('^{}$'.format(ext.number), destination):
                    ext.generate_dialplan(context_el, params)
                    return
            except re.error:
                continue

        # Try outgoing routes
        OutgoingRoute = request.env['connect.freeswitch.outgoing_route'].sudo()
        if OutgoingRoute.generate_dialplan(context_el, params):
            return

        # Fallback: try bridge user directly (for simple digit-only extensions)
        if re.match(r'^\d+$', destination):
            ext = ET.SubElement(context_el, 'extension', name='local_extension')
            condition = ET.SubElement(ext, 'condition',
                field='destination_number', expression=r'^(\d+)$')
            ET.SubElement(condition, 'action', application='set', data='call_timeout=30')
            ET.SubElement(condition, 'action', application='set', data='hangup_after_bridge=true')
            ET.SubElement(condition, 'action', application='set', data='continue_on_fail=true')
            ET.SubElement(condition, 'action', application='bridge', data='user/$1@$${domain}')

    def _add_system_extensions(self, context_el):
        """Add system utility extensions (echo test, etc.)."""
        echo_ext = ET.SubElement(context_el, 'extension', name='echo')
        echo_cond = ET.SubElement(echo_ext, 'condition',
            field='destination_number', expression='^9196$')
        ET.SubElement(echo_cond, 'action', application='answer')
        ET.SubElement(echo_cond, 'action', application='echo')

    def _handle_configuration(self, params):
        """Handle configuration section requests.

        Serves gateway definitions for sofia.conf when gateways are configured in Odoo.
        All other configuration requests fall through to local FreeSWITCH config.
        """
        key_value = params.get('key_value', '')

        _logger.debug("Configuration request: key_value=%s", key_value)

        if key_value == 'sofia.conf':
            return self._get_sofia_config(params)

        return self._not_found()

    def _get_sofia_config(self, params):
        """Serve sofia.conf with gateways from Odoo.

        Returns a sofia configuration containing an external profile
        with all active gateways defined in Odoo. If no gateways exist,
        falls through to local config.
        """
        Gateway = request.env['connect.freeswitch.gateway'].sudo()
        gateways = Gateway.search([('active', '=', True)])

        if not gateways:
            return self._not_found()

        root = ET.Element('document', type='freeswitch/xml')
        section = ET.SubElement(root, 'section', name='configuration')
        config = ET.SubElement(section, 'configuration',
            name='sofia.conf', description='Sofia SIP')

        # Global settings
        global_settings = ET.SubElement(config, 'global_settings')
        ET.SubElement(global_settings, 'param', name='log-level', value='0')

        profiles = ET.SubElement(config, 'profiles')

        # External profile for gateways
        profile = ET.SubElement(profiles, 'profile', name='external')
        settings = ET.SubElement(profile, 'settings')
        ET.SubElement(settings, 'param', name='context', value='public')
        ET.SubElement(settings, 'param', name='sip-port', value='5080')
        ET.SubElement(settings, 'param', name='rtp-timer-name', value='soft')
        ET.SubElement(settings, 'param', name='codec-prefs', value='OPUS,PCMU,PCMA')

        gateways_el = ET.SubElement(profile, 'gateways')
        for gw in gateways:
            gw.generate_sofia_gateway_xml(gateways_el)

        return self._xml_response(root)

    def _xml_response(self, root):
        """Generate HTTP response with XML content."""
        xml_str = ET.tostring(root, encoding='unicode', method='xml')

        # Pretty-print XML for logging
        pretty = pretty_xml(xml_str)
        _logger.debug("XML response:\n%s", pretty)

        return Response(
            xml_str,
            content_type='text/xml; charset=utf-8',
            status=200
        )

    def _not_found(self):
        """Return not found response."""
        root = ET.Element('document', type='freeswitch/xml')
        section = ET.SubElement(root, 'section', name='result')
        ET.SubElement(section, 'result', status='not found')
        return self._xml_response(root)
