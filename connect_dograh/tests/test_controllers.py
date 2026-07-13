# -*- coding: utf-8 -*-
"""Tests for the Dograh -> Odoo control-plane endpoints (Bearer token
auth, uuid_kill dispatch)."""
import json
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import HttpCase

TEST_TOKEN = 'test-dograh-service-token-12345678'


@tagged('post_install', '-at_install', 'connect_dograh')
class TestDograhControllers(HttpCase):

    def setUp(self):
        super().setUp()
        self.settings = self.env['connect.settings'].sudo()
        self.settings.set_param('dograh_service_token', TEST_TOKEN)

    def _post(self, payload, token=TEST_TOKEN, headers=None):
        headers = dict(headers or {})
        headers['Content-Type'] = 'application/json'
        if token is not None:
            headers['Authorization'] = 'Bearer {}'.format(token)
        return self.url_open('/dograh/api/hangup',
                             data=json.dumps(payload), headers=headers)

    def test_hangup_rejects_without_token(self):
        resp = self._post({'call_uuid': 'u1'}, token=None)
        self.assertEqual(resp.status_code, 401)

    def test_hangup_rejects_wrong_token(self):
        resp = self._post({'call_uuid': 'u1'}, token='wrong-token-wrong')
        self.assertEqual(resp.status_code, 401)

    def test_hangup_rejects_when_unconfigured(self):
        # Fail-closed: with no token stored every request is rejected.
        self.settings.set_param('dograh_service_token', False)
        resp = self._post({'call_uuid': 'u1'})
        self.assertEqual(resp.status_code, 401)

    def test_hangup_requires_call_uuid(self):
        resp = self._post({})
        self.assertEqual(resp.status_code, 400)

    def test_hangup_kills_channel(self):
        with patch.object(type(self.settings), 'freeswitch_api',
                          return_value='+OK') as fs_api:
            resp = self._post({'call_uuid': 'uuid-abc'})
        self.assertEqual(resp.status_code, 200)
        args = fs_api.call_args[0]
        self.assertEqual(args[-2:], ('uuid_kill', 'uuid-abc'))

    def test_hangup_channel_already_gone(self):
        with patch.object(type(self.settings), 'freeswitch_api',
                          return_value='-ERR No such channel!'):
            resp = self._post({'call_uuid': 'uuid-gone'})
        self.assertEqual(resp.status_code, 404)

    def test_hangup_freeswitch_unreachable(self):
        with patch.object(type(self.settings), 'freeswitch_api',
                          return_value=False):
            resp = self._post({'call_uuid': 'uuid-abc'})
        self.assertEqual(resp.status_code, 502)
