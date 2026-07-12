# -*- coding: utf-8 -*-
"""Dograh -> Odoo control-plane endpoints (ADR-037).

Dograh's freeswitch provider package calls these to control FreeSWITCH
channels: only Odoo holds the mod_xml_rpc credentials. All routes are
public POST JSON endpoints authenticated by the shared
``dograh_service_token`` (Bearer), executed as the special webhook user,
and declared readonly=False explicitly.
"""
import json
import logging
import secrets

from odoo.http import Controller, Response, request, route

logger = logging.getLogger(__name__)


def check_dograh_auth():
    """Return True when the request carries the valid service token.

    Fail-closed: requests are rejected when no token is configured.
    """
    expected = request.env['connect.settings'].sudo().get_param(
        'dograh_service_token') or ''
    if not expected:
        return False
    auth = request.httprequest.headers.get('Authorization', '')
    if not auth.lower().startswith('bearer '):
        return False
    candidate = auth[7:].strip()
    return secrets.compare_digest(
        candidate.encode('utf-8', 'ignore'),
        expected.encode('utf-8', 'ignore'))


def unauthorized_response():
    """Uniform 401 reply that leaks nothing about the expected token."""
    return Response('Unauthorized', status=401)


class ConnectDograhController(Controller):

    def _parse_body(self):
        try:
            return json.loads(request.httprequest.get_data() or b'{}')
        except ValueError:
            logger.error('Dograh API: invalid JSON body.')
            return None

    def _settings(self):
        return request.env['connect.settings'].with_user(
            request.env.ref('connect.user_connect_webhook')).sudo()

    @route('/dograh/api/originate', methods=['POST'], type='http',
           auth='public', csrf=False, readonly=False)
    def originate(self, **kw):
        if not check_dograh_auth():
            return unauthorized_response()
        body = self._parse_body()
        if body is None:
            return request.make_json_response(
                {'error': 'invalid JSON body'}, status=400)
        if not body.get('to_number') or not body.get('websocket_url'):
            return request.make_json_response(
                {'error': 'to_number and websocket_url are required'},
                status=400)
        result, status = self._settings().dograh_originate(
            body['to_number'], body['websocket_url'],
            from_number=body.get('from_number'),
            run_id=body.get('workflow_run_id'))
        return request.make_json_response(result, status=status or 200)

    @route('/dograh/api/hangup', methods=['POST'], type='http',
           auth='public', csrf=False, readonly=False)
    def hangup(self, **kw):
        if not check_dograh_auth():
            return unauthorized_response()
        body = self._parse_body()
        if body is None or not body.get('call_uuid'):
            return request.make_json_response(
                {'error': 'call_uuid is required'}, status=400)
        call_uuid = body['call_uuid']
        result = self._settings().freeswitch_api('uuid_kill', call_uuid)
        if result is False:
            return request.make_json_response(
                {'error': 'freeswitch unreachable'}, status=502)
        if '-ERR No such channel' in result:
            # Already hung up: the Dograh hangup strategy treats 404 as
            # success (caller ended the call first).
            return request.make_json_response(
                {'error': 'no such channel'}, status=404)
        logger.info('Dograh hangup of %s: %s', call_uuid, result.strip())
        return request.make_json_response({'result': result.strip()})
