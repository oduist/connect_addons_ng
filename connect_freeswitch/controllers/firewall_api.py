# -*- coding: utf-8 -*-
"""HTTP controllers for the firewall service ↔ Odoo direction.

The firewall service (oduist/freeswitch-firewall) calls these endpoints
to pull desired state from Odoo (config, whitelist, blacklist) and to
report what is happening at the kernel level (events, heartbeats,
applied actions). Every request must carry
``Authorization: Bearer <firewall_service_token>``; the token is the
same shared secret the Odoo side already uses for the reverse direction
(``/firewall/sync`` POSTs to the service).

There is no Odoo user behind these calls — the controller runs
``sudo()`` after the token check passes.
"""
import json
import logging
import secrets

from odoo import http
from odoo.http import Response, request

logger = logging.getLogger(__name__)


class FirewallAPIController(http.Controller):

    @staticmethod
    def _check_token():
        expected = request.env['connect.provider.freeswitch.config'].sudo()._get().firewall_service_token or ''
        if not expected:
            return False
        auth = request.httprequest.headers.get('Authorization', '')
        if not auth.lower().startswith('bearer '):
            return False
        return secrets.compare_digest(auth[7:].strip(), expected)

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
    def _read_payload():
        raw = request.httprequest.get_data(as_text=True) or ''
        if not raw:
            return {}
        return json.loads(raw)

    @http.route('/freeswitch/firewall/api/config',
                type='http', auth='none', methods=['GET'], csrf=False)
    def config(self, **_):
        if not self._check_token():
            return self._unauthorized()
        return self._json(
            request.env['connect.firewall.agent'].sudo().fetch_config()
        )

    @http.route('/freeswitch/firewall/api/whitelist',
                type='http', auth='none', methods=['GET'], csrf=False)
    def whitelist(self, **_):
        if not self._check_token():
            return self._unauthorized()
        return self._json(
            request.env['connect.firewall.agent'].sudo().fetch_whitelist()
        )

    @http.route('/freeswitch/firewall/api/blacklist',
                type='http', auth='none', methods=['GET'], csrf=False)
    def blacklist(self, **_):
        if not self._check_token():
            return self._unauthorized()
        return self._json(
            request.env['connect.firewall.agent'].sudo().fetch_blacklist()
        )

    @http.route('/freeswitch/firewall/api/heartbeat',
                type='http', auth='none', methods=['POST'], csrf=False)
    def heartbeat(self, **_):
        if not self._check_token():
            return self._unauthorized()
        try:
            payload = self._read_payload()
        except ValueError:
            return self._json({'error': 'bad_json'}, status=400)
        request.env['connect.firewall.agent'].sudo().report_heartbeat(payload)
        return self._json({'ok': True})

    @http.route('/freeswitch/firewall/api/event',
                type='http', auth='none', methods=['POST'], csrf=False)
    def event(self, **_):
        if not self._check_token():
            return self._unauthorized()
        try:
            payload = self._read_payload()
        except ValueError:
            return self._json({'error': 'bad_json'}, status=400)
        rec_id = request.env['connect.firewall.agent'].sudo().report_event(payload)
        return self._json({'ok': bool(rec_id), 'id': rec_id or False})

    @http.route('/freeswitch/firewall/api/applied',
                type='http', auth='none', methods=['POST'], csrf=False)
    def applied(self, **_):
        if not self._check_token():
            return self._unauthorized()
        try:
            payload = self._read_payload()
        except ValueError:
            return self._json({'error': 'bad_json'}, status=400)
        request.env['connect.firewall.agent'].sudo().report_applied(
            ip=payload.get('ip'),
            action=payload.get('action'),
            status=payload.get('status', 'ok'),
            message=payload.get('message'),
        )
        return self._json({'ok': True})
