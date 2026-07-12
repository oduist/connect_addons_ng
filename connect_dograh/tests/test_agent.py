# -*- coding: utf-8 -*-
"""Tests for connect.dograh.agent: extension linking and dialplan
generation against a mocked Dograh inbound-run webhook (ADR-038)."""
from unittest.mock import patch

from odoo.tests import tagged

from .common import DograhTestCommon, TEST_TOKEN, make_response

DIALPLAN_PARAMS = {
    'Caller-Unique-ID': 'uuid-test-1234',
    'Caller-Caller-ID-Number': '+37120000001',
    'Caller-Destination-Number': '9001',
}

RUN_REPLY = {
    'websocket_url':
        'wss://dograh.example.com/api/v1/telephony/ws/7/1/42',
    'workflow_run_id': 42,
}


@tagged('post_install', '-at_install', 'connect_dograh')
class TestDograhAgent(DograhTestCommon):

    def test_extension_links_agent(self):
        agent = self._create_agent()
        exten = self._create_extension(agent, '9001')
        self.assertEqual(agent.exten, exten)
        self.assertEqual(agent.exten_number, '9001')
        self.assertEqual(exten.dst, agent)

    def test_extension_dst_selection_contains_agent(self):
        selection = dict(
            self.env['connect.freeswitch.exten']._fields['dst'].selection)
        self.assertIn('connect.dograh.agent', selection)

    def test_dialplan_success(self):
        agent = self._create_agent(record_calls=False)
        exten = self._create_extension(agent, '9001')
        with patch('odoo.addons.connect_dograh.models.agent'
                   '.requests.post') as post:
            post.return_value = make_response(200, RUN_REPLY)
            dialplan = exten.generate_dialplan(DIALPLAN_PARAMS)
        # The inbound webhook carried the call identity and auth.
        args, kwargs = post.call_args
        self.assertEqual(
            args[0],
            'https://dograh.example.com/api/v1/telephony/inbound/run')
        self.assertEqual(kwargs['headers']['Authorization'],
                         'Bearer {}'.format(TEST_TOKEN))
        payload = kwargs['json']
        self.assertEqual(payload['provider'], 'freeswitch')
        self.assertEqual(payload['account_id'], 'odoo-test')
        self.assertEqual(payload['call_id'], 'uuid-test-1234')
        self.assertEqual(payload['from_number'], '+37120000001')
        self.assertEqual(payload['to_number'], '9001')
        # The dialplan forks audio to the returned media WebSocket.
        self.assertIn('dograh_agent_{}'.format(agent.id), dialplan)
        self.assertIn('expression="^9001$"', dialplan)
        self.assertIn(
            'uuid_audio_fork(${uuid} start %s mono 16k dograh {} true '
            'true 16000)' % RUN_REPLY['websocket_url'], dialplan)
        self.assertIn('odoo_dograh_run_id=42', dialplan)
        self.assertIn('<action application="park"/>', dialplan)
        self.assertNotIn('record_session', dialplan)

    def test_dialplan_recording_enabled(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'web.base.url', 'https://odoo.example.com')
        agent = self._create_agent(record_calls=True)
        exten = self._create_extension(agent, '9002')
        with patch('odoo.addons.connect_dograh.models.agent'
                   '.requests.post') as post:
            post.return_value = make_response(200, RUN_REPLY)
            dialplan = exten.generate_dialplan(DIALPLAN_PARAMS)
        token = self.settings.get_param('freeswitch_webhook_token')
        self.assertIn('record_session', dialplan)
        self.assertIn(
            'https://odoo.example.com/freeswitch/webhook/recording/'
            '{}/${{uuid}}.wav'.format(token), dialplan)

    def test_dialplan_dograh_rejects(self):
        agent = self._create_agent()
        exten = self._create_extension(agent, '9003')
        with patch('odoo.addons.connect_dograh.models.agent'
                   '.requests.post') as post:
            post.return_value = make_response(
                200, {'error': 'phone_number_not_configured',
                      'message': 'not configured'})
            dialplan = exten.generate_dialplan(DIALPLAN_PARAMS)
        self.assertIn('respond" data="486"', dialplan)
        self.assertNotIn('uuid_audio_fork', dialplan)

    def test_dialplan_dograh_unreachable(self):
        import requests as requests_lib
        agent = self._create_agent()
        exten = self._create_extension(agent, '9004')
        with patch('odoo.addons.connect_dograh.models.agent'
                   '.requests.post') as post:
            post.side_effect = requests_lib.ConnectionError('down')
            dialplan = exten.generate_dialplan(DIALPLAN_PARAMS)
        self.assertIn('respond" data="486"', dialplan)

    def test_dialplan_settings_incomplete(self):
        self.settings.set_param('dograh_api_url', False)
        agent = self._create_agent()
        exten = self._create_extension(agent, '9005')
        with patch('odoo.addons.connect_dograh.models.agent'
                   '.requests.post') as post:
            dialplan = exten.generate_dialplan(DIALPLAN_PARAMS)
        post.assert_not_called()
        self.assertIn('respond" data="486"', dialplan)

    def test_create_extension_action(self):
        agent = self._create_agent()
        action = agent.create_extension()
        self.assertEqual(action['res_model'], 'connect.freeswitch.exten')
        self.assertEqual(
            action['context']['default_dst'],
            'connect.dograh.agent,{}'.format(agent.id))
