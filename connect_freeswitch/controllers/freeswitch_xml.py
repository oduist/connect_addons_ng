# -*- coding: utf-8 -*-
import logging
import re
from xml.dom import minidom

from odoo import http
from odoo.http import request, Response
from odoo.addons.connect.models.settings import debug

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
        debug(request.env['connect.settings'].sudo(), "FreeSWITCH XML request: section=%s, params=%s" % (section, kwargs))

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

        debug(request.env['connect.settings'].sudo(), "Directory request: action=%s, user=%s, domain=%s" % (action, user, domain))

        # User lookup/authentication - user is enough, domain can be empty
        if user:
            return self._get_user_xml(user, domain, params)

        # Full directory request
        if params.get('purpose') == 'gateways':
            return self._not_found()

        return self._get_full_directory(domain)

    def _get_user_xml(self, user, domain, params):
        """Generate XML for a specific user.

        Lookup order:
        1. SIP endpoint by auth_user (SIP registration)
        2. WebRTC user by res.users login (Verto registration)
        3. User by exten_number (bridge to user)
        4. Standalone endpoint by exten_number (bridge to endpoint)
        """
        Endpoint = request.env['connect.endpoint'].sudo()
        ConnectUser = request.env['connect.user'].sudo()

        fs_domain = request.env['connect.settings'].sudo().get_param('freeswitch_domain')
        actual_domain = fs_domain or domain or params.get('sip_auth_realm', '')

        # 1. Search by auth_user (SIP endpoint registration)
        endpoint = Endpoint.search([
            ('auth_user', '=', user),
            ('active', '=', True),
        ], limit=1)

        if endpoint:
            # For bridge requests (not SIP auth), if the endpoint belongs to
            # a user, return the combined dial-string (all endpoints + WebRTC)
            action = params.get('action', '')
            if action != 'sip_auth' and endpoint.connect_user_id:
                return self._directory_for_user_bridge(
                    endpoint.connect_user_id, user, actual_domain)
            return self._directory_for_endpoint(endpoint, user, actual_domain)

        # 2. Search by res.users login (Verto WebRTC registration)
        connect_user = ConnectUser.search([
            ('user.login', '=', user),
            ('webrtc_enabled', '=', True),
            ('active', '=', True),
        ], limit=1)
        if connect_user:
            return self._directory_for_webrtc_user(connect_user, user, actual_domain)

        # 3. Search by exten_number (bridge to user)
        connect_user = ConnectUser.search([
            ('exten_number', '=', user),
            ('active', '=', True),
        ], limit=1)
        if connect_user:
            return self._directory_for_user_bridge(connect_user, user, actual_domain)

        # 4. Search standalone endpoint by exten_number (bridge to endpoint)
        endpoint = Endpoint.search([
            ('exten_number', '=', user),
            ('connect_user_id', '=', False),
            ('active', '=', True),
        ], limit=1)
        if endpoint:
            return self._directory_for_endpoint(endpoint, user, actual_domain)

        debug(request.env['connect.settings'].sudo(), "User not found in Odoo: %s" % user)
        return self._not_found()

    def _directory_for_endpoint(self, endpoint, xml_user_id, domain):
        """Directory entry for a SIP endpoint (registration or bridge)."""
        connect_user = endpoint.connect_user_id

        # Dial-string for this endpoint only (SIP contact)
        dial_string = "${{sofia_contact(*/{auth_user}@{domain})}}".format(
            auth_user=endpoint.auth_user, domain=domain)

        cid_name = connect_user.name if connect_user else endpoint.auth_user
        cid_num = (connect_user.exten_number if connect_user else endpoint.exten_number) or endpoint.auth_user

        return self._render_directory_user(
            xml_user_id=xml_user_id,
            password=endpoint.auth_password or '',
            dial_string=dial_string,
            cid_name=cid_name,
            cid_num=cid_num,
            connect_user_id=str(connect_user.id) if connect_user else '',
            endpoint_id=str(endpoint.id),
            odoo_user_id=str(connect_user.user.id) if connect_user and connect_user.user else '',
            domain=domain,
        )

    def _directory_for_webrtc_user(self, connect_user, xml_user_id, domain):
        """Directory entry for a WebRTC/Verto user registration."""
        dial_string = "${{verto_contact({user_id}@{domain})}}".format(
            user_id=xml_user_id, domain=domain)

        cid_name = connect_user.name
        cid_num = connect_user.exten_number or xml_user_id

        return self._render_directory_user(
            xml_user_id=xml_user_id,
            password=connect_user.webrtc_password or '',
            dial_string=dial_string,
            cid_name=cid_name,
            cid_num=cid_num,
            connect_user_id=str(connect_user.id),
            endpoint_id='',
            odoo_user_id=str(connect_user.user.id) if connect_user.user else '',
            domain=domain,
        )

    def _directory_for_user_bridge(self, connect_user, xml_user_id, domain):
        """Directory entry for bridging to a user (combined dial-string)."""
        dial_parts = []

        # All active SIP endpoints (incoming calls ring all, not just originate_ring)
        endpoints = request.env['connect.endpoint'].sudo().search([
            ('connect_user_id', '=', connect_user.id),
            ('active', '=', True),
            ('auth_user', '!=', False),
        ])
        for ep in endpoints:
            dial_parts.append("${{sofia_contact(*/{auth_user}@{domain})}}".format(
                auth_user=ep.auth_user, domain=domain))

        # WebRTC contact
        if connect_user.webrtc_enabled:
            verto_login = connect_user.user.login
            dial_parts.append("${{verto_contact({user_id}@{domain})}}".format(
                user_id=verto_login, domain=domain))

        dial_string = ",".join(dial_parts)

        cid_name = connect_user.name
        cid_num = connect_user.exten_number or (endpoints[0].auth_user if endpoints else '')

        # Password: use webrtc_password or first endpoint's password (needed for FS XML structure)
        password = connect_user.webrtc_password or (endpoints[0].auth_password if endpoints else '') or ''

        return self._render_directory_user(
            xml_user_id=xml_user_id,
            password=password,
            dial_string=dial_string,
            cid_name=cid_name,
            cid_num=cid_num,
            connect_user_id=str(connect_user.id),
            endpoint_id=str(endpoints[0].id) if endpoints else '',
            odoo_user_id=str(connect_user.user.id) if connect_user.user else '',
            domain=domain,
        )

    def _render_directory_user(self, xml_user_id, password, dial_string,
                                cid_name, cid_num, connect_user_id,
                                endpoint_id, odoo_user_id, domain):
        """Render directory user XML from template."""
        Template = request.env['connect.freeswitch.template'].sudo()
        user_xml = Template.render('directory_user', {
            'xml_user_id': xml_user_id,
            'password': password,
            'dial_string': dial_string,
            'cid_name': cid_name,
            'cid_num': cid_num,
            'connect_user_id': connect_user_id,
            'endpoint_id': endpoint_id,
            'odoo_user_id': odoo_user_id,
        })

        xml_str = ('<document type="freeswitch/xml">'
                   '<section name="directory">'
                   '<domain name="{domain}">'
                   '{body}'
                   '</domain></section></document>').format(
                       domain=domain, body=user_xml)
        return self._xml_response_str(xml_str)

    def _get_full_directory(self, domain):
        """Generate full directory XML with all users."""
        Endpoint = request.env['connect.endpoint'].sudo()
        ConnectUser = request.env['connect.user'].sudo()

        actual_domain = request.env['connect.settings'].sudo().get_param('freeswitch_domain') or domain

        ep_data = []

        # All active SIP endpoints
        endpoints = Endpoint.search([
            ('active', '=', True),
            ('auth_user', '!=', False),
            ('auth_password', '!=', False),
        ])
        for endpoint in endpoints:
            connect_user = endpoint.connect_user_id
            ep_data.append({
                'auth_user': endpoint.auth_user,
                'password': endpoint.auth_password,
                'cid_name': connect_user.name if connect_user else endpoint.auth_user,
                'cid_num': (connect_user.exten_number if connect_user else endpoint.exten_number) or endpoint.auth_user,
                'connect_user_id': str(connect_user.id) if connect_user else '',
                'endpoint_id': str(endpoint.id),
                'odoo_user_id': str(connect_user.user.id) if connect_user and connect_user.user else '',
            })

        # All active WebRTC users
        webrtc_users = ConnectUser.search([
            ('webrtc_enabled', '=', True),
            ('webrtc_password', '!=', False),
            ('active', '=', True),
        ])
        for wu in webrtc_users:
            ep_data.append({
                'auth_user': wu.user.login,
                'password': wu.webrtc_password,
                'cid_name': wu.name,
                'cid_num': wu.exten_number or wu.user.login,
                'connect_user_id': str(wu.id),
                'endpoint_id': '',
                'odoo_user_id': str(wu.user.id) if wu.user else '',
            })

        if not ep_data:
            return self._not_found()

        Template = request.env['connect.freeswitch.template'].sudo()
        body = Template.render('directory_full', {'endpoints': ep_data})

        xml_str = ('<document type="freeswitch/xml">'
                   '<section name="directory">'
                   '<domain name="{domain}">'
                   '{body}'
                   '</domain></section></document>').format(
                       domain=actual_domain, body=body)
        return self._xml_response_str(xml_str)

    def _handle_dialplan(self, params):
        """Handle dialplan section requests.

        Routing logic:
        - public context: inbound DID routing via connect.number
        - default context: extension lookup, then outgoing routes, then fallback
        """
        context = params.get('Caller-Context', params.get('Hunt-Context', 'default'))
        destination = params.get('Caller-Destination-Number', '')

        debug(request.env['connect.settings'].sudo(), "Dialplan request: context=%s, destination=%s" % (context, destination))

        if context == 'public':
            body = self._route_inbound(destination, params)
        else:
            body = self._route_internal(destination, params)

        xml_str = ('<document type="freeswitch/xml">'
                   '<section name="dialplan">'
                   '<context name="{context}">'
                   '{body}'
                   '</context></section></document>').format(
                       context=context, body=body)
        return self._xml_response_str(xml_str)

    def _route_inbound(self, destination, params):
        """Route inbound calls from PSTN trunks via connect.number."""
        Number = request.env['connect.number'].sudo()

        # Try exact match on phone number
        number = Number.search([
            ('phone_number', '=', destination),
        ], limit=1)

        # Try with + prefix if not found
        if not number and not destination.startswith('+'):
            number = Number.search([
                ('phone_number', '=', '+' + destination),
            ], limit=1)

        if number:
            return number.generate_dialplan(params)

        _logger.warning("No DID configured for inbound number: %s", destination)
        return ('<extension name="unmatched_inbound">'
                '<condition field="destination_number" expression=".*">'
                '<action application="respond" data="404"/>'
                '</condition></extension>')

    def _route_internal(self, destination, params):
        """Route internal calls: extensions, outgoing routes, system extensions."""
        Exten = request.env['connect.exten'].sudo()

        parts = []

        # System extensions
        Template = request.env['connect.freeswitch.template'].sudo()
        parts.append(Template.render('dialplan_system', {}))

        # Valet parking slots (park/unpark by dialing slot extension)
        ParkingSlot = request.env['connect.freeswitch.parking.slot'].sudo()
        parking_slot = ParkingSlot.search(
            [('exten', '=', destination), ('active', '=', True)], limit=1)
        if parking_slot:
            webhook_url = request.env['ir.config_parameter'].sudo().get_param(
                'web.base.url') or ''
            parts.append(Template.render('dialplan_valet_parking', {
                'slot': parking_slot.exten,
                'lot_name': 'default',
                'webhook_url': webhook_url,
            }))
            return ''.join(parts)

        # Try exact extension match
        exten = Exten.search([('number', '=', destination)], limit=1)
        if exten:
            parts.append(exten.generate_dialplan(params))
            return ''.join(parts)

        # Try regex pattern match against all extensions
        all_extens = Exten.search([])
        for ext in all_extens:
            try:
                if re.match('^{}$'.format(ext.number), destination):
                    parts.append(ext.generate_dialplan(params))
                    return ''.join(parts)
            except re.error:
                continue

        # Try outgoing routes
        OutgoingRoute = request.env['connect.freeswitch.outgoing_route'].sudo()
        route_xml = OutgoingRoute.generate_dialplan(params)
        if route_xml:
            parts.append(route_xml)
            return ''.join(parts)

        # Fallback: try bridge user directly (for simple digit-only extensions)
        if re.match(r'^\d+$', destination):
            parts.append(
                '<extension name="local_extension">'
                '<condition field="destination_number" expression="^(\\d+)$">'
                '<action application="set" data="call_timeout=30"/>'
                '<action application="set" data="hangup_after_bridge=true"/>'
                '<action application="set" data="continue_on_fail=true"/>'
                '<action application="bridge" data="user/$1@$${domain}"/>'
                '</condition></extension>')

        return ''.join(parts)

    def _handle_configuration(self, params):
        """Handle configuration section requests.

        Serves gateway definitions for sofia.conf when gateways are configured in Odoo.
        All other configuration requests fall through to local FreeSWITCH config.
        """
        key_value = params.get('key_value', '')

        # Configs handled by local static files — skip debug logging
        IGNORED_CONFIGS = ('spandsp.conf', 'fax.conf', 'loopback.conf', 'timezones.conf')
        if key_value in IGNORED_CONFIGS:
            return self._not_found()

        debug(request.env['connect.settings'].sudo(), "Configuration request: key_value=%s" % key_value)

        if key_value == 'sofia.conf':
            return self._get_sofia_config(params)
        elif key_value == 'acl.conf':
            return self._get_acl_config(params)
        elif key_value == 'xml_rpc.conf':
            return self._get_xml_rpc_config(params)

        return self._not_found()

    def _get_sofia_config(self, params):
        """Serve sofia.conf with gateways from Odoo."""
        Gateway = request.env['connect.freeswitch.gateway'].sudo()
        gateways = Gateway.search([('active', '=', True)])

        if not gateways:
            return self._not_found()

        # Render each gateway individually
        gateways_xml = '\n'.join(gw.generate_sofia_gateway_xml() for gw in gateways)

        sofia_log_level = request.env['connect.settings'].sudo().get_param('freeswitch_sofia_log_level') or '0'
        fs_domain = request.env['connect.settings'].sudo().get_param('freeswitch_domain')

        Template = request.env['connect.freeswitch.template'].sudo()
        config_xml = Template.render('config_sofia', {
            'sofia_log_level': sofia_log_level,
            'fs_domain': fs_domain or '',
            'gateways_xml': gateways_xml,
        })

        xml_str = ('<document type="freeswitch/xml">'
                   '<section name="configuration">'
                   '{body}'
                   '</section></document>').format(body=config_xml)
        return self._xml_response_str(xml_str)

    def _get_acl_config(self, params):
        """Serve acl.conf with gateway IP whitelist from Odoo."""
        Gateway = request.env['connect.freeswitch.gateway'].sudo()
        acl_entries = Gateway._get_all_acl_ips()

        Template = request.env['connect.freeswitch.template'].sudo()
        config_xml = Template.render('config_acl', {
            'acl_entries': acl_entries,
        })

        xml_str = ('<document type="freeswitch/xml">'
                   '<section name="configuration">'
                   '{body}'
                   '</section></document>').format(body=config_xml)
        return self._xml_response_str(xml_str)

    def _get_xml_rpc_config(self, params):
        """Serve xml_rpc.conf with credentials from Odoo settings."""
        settings = request.env['connect.settings'].sudo()
        user = settings.get_param('freeswitch_xmlrpc_user')
        password = settings.get_param('freeswitch_xmlrpc_password')

        if not user or not password:
            return self._not_found()

        port = str(settings.get_param('freeswitch_xmlrpc_port') or 8080)

        Template = request.env['connect.freeswitch.template'].sudo()
        config_xml = Template.render('config_xml_rpc', {
            'port': port,
            'user': user,
            'password': password,
        })

        xml_str = ('<document type="freeswitch/xml">'
                   '<section name="configuration">'
                   '{body}'
                   '</section></document>').format(body=config_xml)
        return self._xml_response_str(xml_str)

    def _xml_response_str(self, xml_str):
        """Generate HTTP response from an XML string."""
        # Pretty-print XML for logging
        pretty = pretty_xml(xml_str)
        debug(request.env['connect.settings'].sudo(), "XML response:\n%s" % pretty)

        return Response(
            xml_str,
            content_type='text/xml; charset=utf-8',
            status=200
        )

    def _not_found(self):
        """Return not found response."""
        xml_str = ('<document type="freeswitch/xml">'
                   '<section name="result">'
                   '<result status="not found"/>'
                   '</section></document>')
        return self._xml_response_str(xml_str)
