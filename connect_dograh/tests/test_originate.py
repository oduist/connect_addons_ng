# -*- coding: utf-8 -*-
"""Tests for Dograh-initiated outbound calls: the dograh_originate
model method, the /dograh/api/originate endpoint and the
dograh_outbound dialplan hook."""
import base64
import json
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from .common import DograhTestCommon, TEST_TOKEN

WS_URL = 'wss://dograh.example.com/api/v1/telephony/ws/7/1/42'


@tagged('post_install', '-at_install', 'connect_dograh')
class TestDograhOriginate(DograhTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.gateway = cls.env['connect.freeswitch.gateway'].create({
            'name': 'testgw',
            'proxy': 'sip.test.example.com',
        })
        cls.route = cls.env['connect.freeswitch.outgoing_route'].create({
            'name': 'International',
            'pattern': r'^\+\d{7,}$',
            'gateway': cls.gateway.id,
        })

    def _originate(self, to_number='+37120000001', ws_url=WS_URL, **kwargs):
        with patch.object(type(self.settings), 'freeswitch_api',
                          return_value='+OK') as fs_api:
            result, status = self.settings.dograh_originate(
                to_number, ws_url, **kwargs)
        return result, status, fs_api

    def test_originate_success(self):
        result, status, fs_api = self._originate(run_id=42)
        self.assertIsNone(status)
        self.assertTrue(result['call_uuid'])
        command, cmd = fs_api.call_args[0][-2:]
        self.assertEqual(command, 'originate')
        self.assertIn('sofia/gateway/testgw/+37120000001', cmd)
        self.assertIn('dograh_ws_url={}'.format(WS_URL), cmd)
        self.assertIn('odoo_dograh_run_id=42', cmd)
        self.assertIn('odoo_call_direction=outgoing', cmd)
        self.assertIn(
            'origination_uuid={}'.format(result['call_uuid']), cmd)
        self.assertTrue(cmd.endswith('dograh_outbound XML default'))

    def test_originate_uses_default_callerid(self):
        self.env['connect.freeswitch.outgoing_callerid'].create({
            'friendly_name': 'Main',
            'number': '+37167777777',
            'is_default': True,
        })
        result, status, fs_api = self._originate()
        self.assertIsNone(status)
        self.assertIn('origination_caller_id_number=+37167777777',
                      fs_api.call_args[0][-1])
        self.assertEqual(result['from_number'], '+37167777777')

    def test_originate_explicit_from_number(self):
        result, status, fs_api = self._originate(from_number='+37168888888')
        self.assertIsNone(status)
        self.assertIn('origination_caller_id_number=+37168888888',
                      fs_api.call_args[0][-1])

    def test_originate_invalid_number(self):
        result, status, _ = self._originate(to_number='+371;rm -rf')
        self.assertEqual(status, 400)

    def test_originate_invalid_ws_url(self):
        # Metacharacters would break the originate dialstring parser.
        result, status, _ = self._originate(
            ws_url="wss://host/ws/1'},{'x")
        self.assertEqual(status, 400)

    def test_originate_no_route(self):
        result, status, _ = self._originate(to_number='12345')
        self.assertEqual(status, 404)

    def test_originate_freeswitch_error(self):
        with patch.object(type(self.settings), 'freeswitch_api',
                          return_value='-ERR NO_ANSWER'):
            result, status = self.settings.dograh_originate(
                '+37120000001', WS_URL)
        self.assertEqual(status, 502)
        self.assertIn('NO_ANSWER', result['error'])


@tagged('post_install', '-at_install', 'connect_dograh')
class TestDograhOriginateHttp(HttpCase):

    def setUp(self):
        super().setUp()
        self.settings = self.env['connect.settings'].sudo()
        self.settings.set_param('dograh_service_token', TEST_TOKEN)
        gateway = self.env['connect.freeswitch.gateway'].create({
            'name': 'testgw-http',
            'proxy': 'sip.test.example.com',
        })
        self.env['connect.freeswitch.outgoing_route'].create({
            'name': 'International',
            'pattern': r'^\+\d{7,}$',
            'gateway': gateway.id,
        })

    def _post(self, payload, token=TEST_TOKEN):
        headers = {'Content-Type': 'application/json'}
        if token is not None:
            headers['Authorization'] = 'Bearer {}'.format(token)
        return self.url_open('/dograh/api/originate',
                             data=json.dumps(payload), headers=headers)

    def test_originate_rejects_without_token(self):
        resp = self._post({'to_number': '+37120000001',
                           'websocket_url': WS_URL}, token=None)
        self.assertEqual(resp.status_code, 401)

    def test_originate_requires_fields(self):
        resp = self._post({'to_number': '+37120000001'})
        self.assertEqual(resp.status_code, 400)

    def test_originate_endpoint(self):
        with patch.object(type(self.settings), 'freeswitch_api',
                          return_value='+OK'):
            resp = self._post({'to_number': '+37120000001',
                               'websocket_url': WS_URL,
                               'workflow_run_id': 42})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['call_uuid'])
        self.assertEqual(data['status'], 'answered')

    def test_outbound_dialplan_hook(self):
        # The dograh_outbound hunt destination must serve the audio_fork
        # dialplan through the standard mod_xml_curl endpoint.
        token = self.settings.get_param('freeswitch_webhook_token')
        cred = base64.b64encode(
            ('freeswitch:%s' % token).encode()).decode()
        resp = self.url_open(
            '/freeswitch/xml',
            data={'section': 'dialplan',
                  'Caller-Context': 'default',
                  'Caller-Destination-Number': 'dograh_outbound'},
            headers={'Authorization': 'Basic %s' % cred})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('dograh_outbound', resp.text)
        self.assertIn('uuid_audio_fork', resp.text)
        self.assertIn('${dograh_ws_url}', resp.text)
