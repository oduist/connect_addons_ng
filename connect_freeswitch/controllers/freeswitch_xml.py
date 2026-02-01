# -*- coding: utf-8 -*-
import logging
from xml.etree import ElementTree as ET

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


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

        # 1. Сначала ищем по auth_user (для регистрации/логина)
        endpoint = Endpoint.search([
            ('auth_user', '=', user),
            ('active', '=', True),
            '|', ('sip_enabled', '=', True), ('webrtc_enabled', '=', True)
        ], limit=1)

        # 2. Если не нашли, ищем по extension (для входящего звонка/bridge)
        if not endpoint:
            connect_user = ConnectUser.search([
                ('extension', '=', user),
                ('active', '=', True)
            ], limit=1)
            if connect_user:
                # Берем первый активный эндпоинт этого человека
                endpoint = Endpoint.search([
                    ('connect_user_id', '=', connect_user.id),
                    ('active', '=', True),
                    '|', ('sip_enabled', '=', True), ('webrtc_enabled', '=', True)
                ], limit=1)

        if not endpoint:
            _logger.debug("User not found in Odoo: %s", user)
            return self._not_found()

        connect_user = endpoint.connect_user_id

        # КРИТИЧНО: FS ожидает, что ID в XML совпадет с запрашиваемым 'user'
        # Если запрашивали '1000', отдаем '1000', даже если это эндпоинт 'admin'
        xml_user_id = user

        actual_domain = endpoint.domain or domain or params.get('sip_auth_realm') or '80.246.208.201'

        root = ET.Element('document', type='freeswitch/xml')
        section = ET.SubElement(root, 'section', name='directory')
        domain_el = ET.SubElement(section, 'domain', name=actual_domain)

        # User ID теперь динамический
        user_el = ET.SubElement(domain_el, 'user', id=xml_user_id)

        # Params
        user_params = ET.SubElement(user_el, 'params')
        ET.SubElement(user_params, 'param', name='password', value=endpoint.auth_password or '')
        ET.SubElement(user_params, 'param', name='vm-password', value=endpoint.auth_password or '')

        # Конструируем dial-string, чтобы работал bridge(user/1000)
        # Это говорит FS: "Чтобы найти этого юзера, звони и на SIP, и на Verto"
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

        # Caller ID берем из связанного сотрудника
        cid_name = connect_user.name or endpoint.auth_user
        cid_num = connect_user.extension or endpoint.auth_user

        ET.SubElement(variables, 'variable', name='effective_caller_id_name', value=cid_name)
        ET.SubElement(variables, 'variable', name='effective_caller_id_number', value=cid_num)
        ET.SubElement(variables, 'variable', name='outbound_caller_id_name', value=cid_name)
        ET.SubElement(variables, 'variable', name='outbound_caller_id_number', value=cid_num)

        # Odoo Tracking
        ET.SubElement(variables, 'variable', name='odoo_connect_user_id', value=str(connect_user.id))
        ET.SubElement(variables, 'variable', name='odoo_endpoint_id', value=str(endpoint.id))
        if connect_user.user_id:
            ET.SubElement(variables, 'variable', name='odoo_user_id', value=str(connect_user.user_id.id))

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
            ET.SubElement(variables, 'variable', name='effective_caller_id_number', value=connect_user.extension or endpoint.auth_user)
            ET.SubElement(variables, 'variable', name='outbound_caller_id_name', value=connect_user.name or endpoint.auth_user)
            ET.SubElement(variables, 'variable', name='outbound_caller_id_number', value=connect_user.extension or endpoint.auth_user)
            ET.SubElement(variables, 'variable', name='odoo_connect_user_id', value=str(connect_user.id))
            ET.SubElement(variables, 'variable', name='odoo_endpoint_id', value=str(endpoint.id))
            if connect_user.user_id:
                ET.SubElement(variables, 'variable', name='odoo_user_id', value=str(connect_user.user_id.id))

        return self._xml_response(root)

    def _handle_dialplan(self, params):
        """Handle dialplan section requests."""
        context = params.get('Caller-Context', params.get('Hunt-Context', 'default'))
        destination = params.get('Caller-Destination-Number', '')

        _logger.debug("Dialplan request: context=%s, destination=%s", context, destination)

        root = ET.Element('document', type='freeswitch/xml')
        section = ET.SubElement(root, 'section', name='dialplan')
        context_el = ET.SubElement(section, 'context', name=context)

        # Local extension dialing
        extension = ET.SubElement(context_el, 'extension', name='local_extension')
        condition = ET.SubElement(extension, 'condition', field='destination_number', expression=r'^(\d+)$')
        ET.SubElement(condition, 'action', application='set', data='call_timeout=30')
        ET.SubElement(condition, 'action', application='set', data='hangup_after_bridge=true')
        ET.SubElement(condition, 'action', application='set', data='continue_on_fail=true')
        ET.SubElement(condition, 'action', application='bridge', data='user/$1@$${domain}')

        # Echo test
        echo_ext = ET.SubElement(context_el, 'extension', name='echo')
        echo_cond = ET.SubElement(echo_ext, 'condition', field='destination_number', expression='^9196$')
        ET.SubElement(echo_cond, 'action', application='answer')
        ET.SubElement(echo_cond, 'action', application='echo')

        return self._xml_response(root)

    def _handle_configuration(self, params):
        """Handle configuration section requests."""
        key_value = params.get('key_value', '')

        _logger.debug("Configuration request: key_value=%s", key_value)

        # Return not found - let FreeSWITCH use local config
        return self._not_found()

    def _xml_response(self, root):
        """Generate HTTP response with XML content."""
        xml_str = ET.tostring(root, encoding='unicode', method='xml')

        # Pretty-print XML for logging
        from xml.dom import minidom
        dom = minidom.parseString(xml_str)
        pretty_xml = '\n'.join(line for line in dom.toprettyxml(indent='  ').split('\n') if line.strip() and not line.startswith('<?xml'))
        _logger.debug("XML response:\n%s", pretty_xml)

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
