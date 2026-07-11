# -*- coding: utf-8 -*-
"""Shared-token authentication for Infobip -> Odoo webhook endpoints.

Infobip does not sign webhooks (no X-Twilio-Signature analog), so every
request must present the infobip_webhook_token shared secret, either
embedded into the webhook URL (?token=) or as the password part of the
Basic Auth credentials configured on the Infobip forwarding profile.
Fail-closed: requests are rejected when no token is configured, unless
verification is explicitly disabled (infobip_verify_requests). ADR-035.
"""
import base64
import binascii
import secrets

from odoo.http import request, Response


def check_infobip_webhook_auth():
    """Return True when the request carries the valid webhook token."""
    settings = request.env['connect.settings'].sudo()
    if not settings.get_param('infobip_verify_requests'):
        return True
    expected = settings.get_param('infobip_webhook_token') or ''
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

    # Compare as bytes: secrets.compare_digest raises TypeError on a str
    # containing non-ASCII, which would turn an attacker-supplied non-ASCII
    # token into a 500 instead of the uniform 401 on this open endpoint.
    expected_b = expected.encode('utf-8', 'ignore')
    return any(
        secrets.compare_digest(candidate.encode('utf-8', 'ignore'), expected_b)
        for candidate in candidates
    )


def unauthorized_response():
    """Uniform 401 reply that leaks nothing about the expected token."""
    return Response('Unauthorized', status=401)
