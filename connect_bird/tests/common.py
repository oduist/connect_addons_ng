# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
from unittest.mock import patch

from odoo.tests import TransactionCase, new_test_user

from odoo.addons.connect_bird.models.settings import Settings as BirdSettings

# Standard-Webhooks style secret: whsec_ + base64 payload.
TEST_SIGNING_SECRET = 'whsec_' + base64.b64encode(
    b'connect-bird-test-secret').decode()


class FakeResponse:
    """Minimal httpx.Response stand-in."""

    def __init__(self, status_code=200, json_data=None, content=b'{}',
                 text=''):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.content = content
        self.text = text or (content.decode('utf-8', 'ignore')
                             if content else '')

    def json(self):
        if isinstance(self._json, Exception):
            raise self._json
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError(
                'error', request=None, response=None)


class BirdApiMock:
    """Callable that replaces connect.settings.bird_request.

    ``responses`` maps (method, path) to a dict/False or a callable
    receiving (payload, params); unmatched calls return ``default``.
    Non-descriptor class attribute: called without the model as first arg.
    """

    def __init__(self, responses=None, default=None):
        self.calls = []
        self.responses = responses or {}
        self.default = {} if default is None else default

    def __call__(self, method, path, payload=None, params=None,
                 timeout=15, raise_exc=True):
        self.calls.append({
            'method': method, 'path': path,
            'payload': payload, 'params': params,
        })
        handler = self.responses.get((method, path), self.default)
        if callable(handler):
            return handler(payload, params)
        return handler

    def calls_to(self, method, path):
        return [c for c in self.calls
                if c['method'] == method and c['path'] == path]


def bird_sign(webhook_id, timestamp, body, secret=TEST_SIGNING_SECRET):
    """Reference implementation of the Standard Webhooks signature."""
    key = base64.b64decode(secret.split('_', 1)[1])
    signed = '{}.{}.'.format(webhook_id, timestamp).encode() + body
    return 'v1,' + base64.b64encode(
        hmac.new(key, signed, hashlib.sha256).digest()).decode()


def patch_bird_request(mock):
    return patch.object(BirdSettings, 'bird_request', new=mock)


class BirdTestCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Settings = cls.env['connect.settings'].sudo()
        Settings.set_param('bird_access_key', 'bk_eu1_testkey')
        Settings.set_param('bird_webhook_signing_key', TEST_SIGNING_SECRET)
        cls.env['ir.config_parameter'].sudo().set_param(
            'connect.api_url', 'https://odoo.example.com')
        cls.settings = Settings.search([], limit=1)

    @classmethod
    def _create_connect_user(cls, login, **kwargs):
        odoo_user = new_test_user(cls.env, login=login)
        vals = {'user': odoo_user.id}
        vals.update(kwargs)
        return cls.env['connect.user'].with_context(
            no_clear_cache=True).create(vals)

    @classmethod
    def _make_number(cls, number='+15550001', capabilities='sms', **kwargs):
        vals = {
            'sid': 'num-{}'.format(number),
            'number': number,
            'name': 'Test {}'.format(number),
            'status': 'active',
            'capabilities': capabilities,
        }
        vals.update(kwargs)
        return cls.env['connect.bird.number'].create(vals)
