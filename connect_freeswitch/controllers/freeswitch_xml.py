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

        # 2. Search by Verto WebRTC login (format: <login-local><res.users.id>).
        # The login is built without '@' because mod_verto splits the JSON-RPC
        # login on '@' to derive the SIP realm; see
        # specs/decisions/016-verto-login-uses-user-id.md.
        res_user = ConnectUser._resolve_verto_login(user)
        if res_user:
            connect_user = ConnectUser.search([
                ('user', '=', res_user.id),
                ('webrtc_enabled', '=', True),
                ('active', '=', True),
            ], limit=1)
            if connect_user:
                return self._directory_for_webrtc_user(
                    connect_user, user, actual_domain)

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
        """Directory entry for a WebRTC/Verto user registration.

        xml_user_id is the Verto login string sent by mod_verto:
        ``<login-local-part><res.users.id>`` (e.g. ``litnimax42``). See
        specs/decisions/016-verto-login-uses-user-id.md.
        """
        dial_string = "${{verto_contact({user_id}@{domain})}}".format(
            user_id=xml_user_id, domain=domain)

        cid_name = connect_user.name
        # Avoid surfacing the internal user.id as caller-id-number; fall back
        # to the user's name so the called party sees something meaningful.
        cid_num = connect_user.exten_number or connect_user.name or xml_user_id

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

        # WebRTC contact: address by the same Verto login string the JS
        # softphone uses to register (<login-local><res.users.id>). See
        # specs/decisions/016-verto-login-uses-user-id.md.
        if connect_user.webrtc_enabled and connect_user.user:
            verto_login = connect_user._get_verto_login()
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

        # All active WebRTC users.
        # Verto users are keyed by the same login the JS softphone sends:
        # <login-local><res.users.id>. See
        # specs/decisions/016-verto-login-uses-user-id.md.
        webrtc_users = ConnectUser.search([
            ('webrtc_enabled', '=', True),
            ('webrtc_password', '!=', False),
            ('active', '=', True),
        ])
        for wu in webrtc_users:
            if not wu.user:
                continue
            verto_login = wu._get_verto_login()
            ep_data.append({
                'auth_user': verto_login,
                'password': wu.webrtc_password,
                'cid_name': wu.name,
                'cid_num': wu.exten_number or wu.name or verto_login,
                'connect_user_id': str(wu.id),
                'endpoint_id': '',
                'odoo_user_id': str(wu.user.id),
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
        # Hunt-* reflects the CURRENT routing lookup (e.g. after
        # execute_extension/transfer to a new destination), while Caller-* is
        # the original A-leg destination. Prefer Hunt when present so that
        # in-call hops (like the IVR's cf_call_<id>_<digit> landing extension)
        # are routed correctly.
        context = params.get('Hunt-Context') or params.get('Caller-Context') or 'default'
        destination = params.get('Hunt-Destination-Number') or params.get('Caller-Destination-Number', '')

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

        # Match tolerating an optional leading '+' between the trunk format and
        # the stored DID (see connect.number._find_by_did).
        number = Number._find_by_did(destination)

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

        # IVR user-choice landing extension: bind_digit_action in dialplan_ivr
        # transfers here when a user-typed choice is picked. Sets per-call
        # variables and bridges to the user.
        ivr_choice = re.match(r'^cf_call_(\d+)_(.+)$', destination)
        if ivr_choice:
            cf = request.env['connect.callflow'].sudo().browse(int(ivr_choice.group(1)))
            if cf.exists():
                choice_xml = cf._generate_ivr_choice_dialplan(ivr_choice.group(2))
                if choice_xml:
                    parts.append(choice_xml)
                    return ''.join(parts)

        # IVR catch-all (invalid DTMF) extension.
        ivr_invalid = re.match(r'^cf_invalid_(\d+)$', destination)
        if ivr_invalid:
            cf = request.env['connect.callflow'].sudo().browse(int(ivr_invalid.group(1)))
            if cf.exists():
                invalid_xml = cf._generate_ivr_invalid_dialplan()
                if invalid_xml:
                    parts.append(invalid_xml)
                    return ''.join(parts)

        # FS Queue by internal handle: a callflow / IVR fallback transfers to
        # fs_fifo_<id> when the queue has no user-facing extension (ADR-026).
        fifo_handle = re.match(r'^fs_fifo_(\d+)$', destination)
        if fifo_handle:
            fifo = request.env['connect.fs_fifo'].sudo().browse(
                int(fifo_handle.group(1)))
            if fifo.exists():
                parts.append(fifo.generate_dialplan(params))
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
        elif key_value == 'fifo.conf':
            return self._get_fifo_config(params)

        return self._not_found()

    def _get_sofia_config(self, params):
        """Serve sofia.conf with the external (TLS-capable) profile and any
        configured gateways.

        The external profile is rendered **unconditionally** — SIP endpoints
        register against it and modules can bridge via ``sofia/external/sip:…``
        even when no gateway records exist. Returning "not found" here when
        there are no gateways left the profile unable to start on a fresh env
        (ODU-45). Gateways are rendered into the profile only when present.
        """
        Gateway = request.env['connect.freeswitch.gateway'].sudo()
        gateways = Gateway.search([('active', '=', True)])

        # Render each gateway individually (empty string if none).
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

    def _get_fifo_config(self, params):
        """Serve fifo.conf.xml with static outbound consumers for every FS Queue.

        Dialplan does `fifo <name> in` to enqueue the caller. Thanks to
        `outbound-strategy=ringall` and the static `<member>` list, mod_fifo
        originates all member dial-strings in parallel; the first to answer
        takes the caller from the queue.
        """
        FsFifo = request.env['connect.fs_fifo'].sudo()
        fifos = FsFifo.search([])

        fs_domain = request.env['connect.settings'].sudo().get_param(
            'freeswitch_domain') or '${domain}'

        fifo_data = []
        for fifo in fifos:
            members = []
            for user in fifo.member_user_ids:
                ds = fifo._member_dial_string(fs_domain, user=user)
                if ds:
                    members.append(ds)
            for endpoint in fifo.member_endpoint_ids:
                ds = fifo._member_dial_string(fs_domain, endpoint=endpoint)
                if ds:
                    members.append(ds)
            if not members:
                continue
            fifo_data.append({
                'name': 'fs_fifo_{}'.format(fifo.id),
                'member_dial_strings': members,
                'max_wait': fifo.max_wait_time or 60,
            })

        Template = request.env['connect.freeswitch.template'].sudo()
        config_xml = Template.render('config_fifo', {'fifos': fifo_data})

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
