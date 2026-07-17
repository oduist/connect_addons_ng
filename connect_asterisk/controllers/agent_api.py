# -*- coding: utf-8 -*-
"""HTTP controllers for agent bootstrap and dialplan-assist lookups.

These routes only read admin-level configuration (AMI credentials,
templates) or resolve numbers to names/dialstrings for the customer's
dialplan via CURL(). They follow the firewall pattern (ADR-015):
``Authorization: Bearer <asterisk_agent_token>`` checked with
``secrets.compare_digest``, then ``sudo()``. The legacy IP allowlist
(``permit_ip_addresses``) is replaced by the Bearer token.

Lookup routes return plain text for trivial consumption from the
dialplan: ``Set(CALLERID(name)=${CURL(https://odoo/asterisk/api/...)})``.
"""
import json
import logging
import secrets

from odoo import http
from odoo.http import Response, request

logger = logging.getLogger(__name__)


class AsteriskAgentAPIController(http.Controller):

    @staticmethod
    def _check_token():
        expected = request.env['connect.settings'].sudo().get_param(
            'asterisk_agent_token'
        ) or ''
        if not expected:
            return False
        auth = request.httprequest.headers.get('Authorization', '')
        token = ''
        if auth.lower().startswith('bearer '):
            token = auth[7:].strip()
        elif request.params.get('token'):
            # Dialplan CURL() cannot set headers in old Asterisk versions;
            # accept the token as a query parameter for lookup routes.
            token = request.params['token']
        if not token:
            return False
        return secrets.compare_digest(token, expected)

    @staticmethod
    def _json(payload, status=200):
        return Response(
            json.dumps(payload, default=str),
            status=status,
            content_type='application/json',
        )

    @classmethod
    def _unauthorized(cls):
        return Response(
            json.dumps({'error': 'unauthorized'}),
            status=401,
            content_type='application/json',
            headers=[('WWW-Authenticate', 'Bearer')],
        )

    @staticmethod
    def _text(payload):
        return Response(payload or '', status=200,
                        content_type='text/plain')

    @http.route('/asterisk/api/config',
                type='http', auth='none', methods=['GET'], csrf=False)
    def config(self, **_):
        """Agent bootstrap: AMI credentials, event filter, recording flag."""
        if not self._check_token():
            return self._unauthorized()
        return self._json(
            request.env['connect.settings'].sudo().asterisk_get_agent_config()
        )

    @http.route('/asterisk/api/get_caller_name',
                type='http', auth='none', methods=['GET'], csrf=False,
                readonly=False)
    def get_caller_name(self, number=None, **_):
        if not self._check_token():
            return self._unauthorized()
        number = (number or '').replace(' ', '')
        if not number:
            return self._text('')
        partner = request.env['res.partner'].sudo().get_partner_by_number(
            number)
        return self._text(partner.name if partner else '')

    @http.route('/asterisk/api/get_partner_manager',
                type='http', auth='none', methods=['GET'], csrf=False,
                readonly=False)
    def get_partner_manager(self, number=None, exten=None, **_):
        """Return the dialstring (or extension) of the partner's salesperson
        so the dialplan can route the caller to their manager."""
        if not self._check_token():
            return self._unauthorized()
        number = (number or '').replace(' ', '')
        if not number:
            return self._text('')
        partner = request.env['res.partner'].sudo().get_partner_by_number(
            number)
        if not partner or not partner.user_id:
            return self._text('')
        connect_user = request.env['connect.user'].sudo().search(
            [('user', '=', partner.user_id.id)], limit=1)
        if not connect_user:
            return self._text('')
        if exten:
            return self._text(connect_user.asterisk_exten_number or '')
        channels = connect_user.asterisk_endpoint_ids.filtered(
            lambda e: e.asterisk_originate_enabled and e.asterisk_channel
        ).mapped('asterisk_channel')
        return self._text('&'.join(channels))

    @http.route('/asterisk/api/get_user_data_by_did',
                type='http', auth='none', methods=['GET'], csrf=False,
                readonly=False)
    def get_user_data_by_did(self, did=None, **_):
        """Resolve a DID to the user's dialstring for dialplan routing."""
        if not self._check_token():
            return self._unauthorized()
        did = (did or '').replace(' ', '')
        if not did:
            return self._text('')
        number = request.env['connect.asterisk.number'].sudo().search(
            [('phone_number', 'in', [did, '+' + did])], limit=1)
        connect_user = number.user if number else False
        if not connect_user:
            return self._text('')
        channels = connect_user.asterisk_endpoint_ids.filtered(
            lambda e: e.asterisk_originate_enabled and e.asterisk_channel
        ).mapped('asterisk_channel')
        return self._text('&'.join(channels))

    @http.route('/asterisk/api/sip_peers',
                type='http', auth='none', methods=['GET'], csrf=False)
    def sip_peers(self, **_):
        """Render the pjsip wizard config for all Asterisk endpoints.

        The administrator includes the output on the PBX, e.g.:
        #exec curl -s "https://odoo/asterisk/api/sip_peers?token=..."
        """
        if not self._check_token():
            return self._unauthorized()
        env = request.env
        endpoints = env['connect.asterisk.endpoint'].sudo().search(
            [('asterisk_sip_user', '!=', False)])
        Template = env['connect.asterisk.template'].sudo()
        chunks = [Template.render('sip_peer_header', {})]
        for endpoint in endpoints:
            if not endpoint.asterisk_sip_password:
                continue
            chunks.append(Template.render('sip_peer', {
                'sip_user': endpoint.asterisk_sip_user,
                'sip_password': endpoint.asterisk_sip_password,
                'transport': endpoint.asterisk_sip_transport or 'udp',
                'name': endpoint.name,
            }))
        return self._text('\n'.join(chunks))

    @http.route('/asterisk/api/manager_conf',
                type='http', auth='none', methods=['GET'], csrf=False)
    def manager_conf(self, **_):
        """Render the manager.conf user snippet for the agent AMI account."""
        if not self._check_token():
            return self._unauthorized()
        settings = request.env['connect.settings'].sudo()
        return self._text(
            request.env['connect.asterisk.template'].sudo().render(
                'manager_conf', {
                    'ami_user': settings.get_param('asterisk_ami_user')
                                or 'connect-agent',
                    'ami_password': settings.get_param('asterisk_ami_password')
                                    or '',
                }))
