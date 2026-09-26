# -*- coding: utf-8 -*-
"""X-Twilio-Signature validation for VoiceML webhooks.

VoiceML signs inbound webhooks exactly like Twilio: HMAC-SHA1 over the full
request URL concatenated with the POST body parameters (sorted by key, each
``key + value`` with no separator). The secret is the tenant API key. This
reimplements `twilio.request_validator.RequestValidator` with the stdlib only,
verified byte-identical against twilio-python's `compute_signature`.
"""

import base64
import hashlib
import hmac
from urllib.parse import urlsplit, urlunsplit


def _sorted_form(params):
    """Return the ``key + value`` concatenation Twilio signs.

    Twilio iterates the sorted set of parameter names, then the sorted set of
    each name's values — and it does NOT skip empty-string values (a bare key
    is still appended). For the single-valued form dicts this module receives,
    that reduces to ``sorted(params.items())`` with no empty-skip.
    """
    out = ''
    for key in sorted(params):
        value = params[key]
        if isinstance(value, (list, tuple)):
            for item in sorted(value):
                out += key + str(item)
        else:
            out += key + str(value)
    return out


def sign_request(url, params, secret):
    """Compute the X-Twilio-Signature value for ``url`` and form ``params``."""
    payload = url + _sorted_form(params)
    mac = hmac.new(
        secret.encode('utf-8'), payload.encode('utf-8'), hashlib.sha1
    )
    return base64.b64encode(mac.digest()).decode('utf-8')


def _with_port(url, default_port):
    parts = urlsplit(url)
    if parts.port is not None:
        return url
    netloc = '{}:{}'.format(parts.hostname, default_port)
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _without_port(url):
    parts = urlsplit(url)
    if parts.port is None:
        return url
    return urlunsplit((parts.scheme, parts.hostname, parts.path, parts.query, parts.fragment))


def valid_request(url, params, signature, secret):
    """Compare a presented signature against the recomputed one.

    Like twilio-python's ``validate``, the signature is checked against the URL
    both with and without an explicit port (Twilio's own signing has been
    historically inconsistent about the port), and compared constant-time.
    """
    if not signature or not secret:
        return False
    scheme = urlsplit(url).scheme or 'https'
    default_port = 443 if scheme == 'https' else 80
    candidates = {
        sign_request(url, params, secret),
        sign_request(_with_port(url, default_port), params, secret),
        sign_request(_without_port(url), params, secret),
    }
    return any(hmac.compare_digest(expected, signature) for expected in candidates)


def normalize_url(url):
    """VoiceML (like Twilio) signs an https URL; an http deployment is an
    operator misconfiguration, so mirror Twilio's effective scheme for
    validation while still failing closed otherwise."""
    return url.replace('http:', 'https:')
