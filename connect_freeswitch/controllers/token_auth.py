# -*- coding: utf-8 -*-
"""Shared-token authentication for FreeSWITCH -> Odoo HTTP endpoints.

Every request FreeSWITCH makes to Odoo (/freeswitch/xml via mod_xml_curl,
/freeswitch/webhook/cdr via mod_xml_cdr, /freeswitch/webhook/parking via
the dialplan curl application and /freeswitch/webhook/recording via
record_session) must present the freeswitch_webhook_token shared secret.
Fail-closed: requests are rejected when no token is configured. ADR-025.
"""
import base64
import binascii
import secrets

from odoo.http import request, Response


def check_fs_webhook_auth(token_from_path=None):
    """Return True when the request carries the valid webhook token.

    Accepted transports, in order:
    - Authorization: Basic — the password part (mod_xml_curl
      gateway-credentials, mod_xml_cdr cred);
    - Authorization: Bearer — symmetry with the firewall API;
    - ``token`` query/form parameter (dialplan curl application);
    - an explicit path segment passed by the caller (recording uploads,
      where a query string would break record_session format detection).
    """
    expected = request.env['connect.settings'].sudo().get_param(
        'freeswitch_webhook_token'
    ) or ''
    if not expected:
        return False

    candidates = []
    auth = request.httprequest.headers.get('Authorization', '')
    if auth.lower().startswith('basic '):
        try:
            decoded = base64.b64decode(auth[6:].strip()).decode('utf-8')
            candidates.append(decoded.split(':', 1)[-1])
        except (binascii.Error, UnicodeDecodeError):
            pass
    elif auth.lower().startswith('bearer '):
        candidates.append(auth[7:].strip())
    param_token = request.httprequest.values.get('token')
    if param_token:
        candidates.append(param_token)
    if token_from_path:
        candidates.append(token_from_path)

    return any(
        secrets.compare_digest(candidate, expected) for candidate in candidates
    )


def unauthorized_response():
    """Uniform 401 reply that leaks nothing about the expected token."""
    return Response('Unauthorized', status=401)
