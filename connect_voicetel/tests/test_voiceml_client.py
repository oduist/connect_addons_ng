# -*- coding: utf-8 -*-
"""The VoiceML SDK client configuration (ADR-066 as amended)."""
from voiceml import Client

from odoo.tests import tagged

from .common import VoiceTelTestCommon


@tagged('at_install', '-post_install')
class TestVoiceMLClient(VoiceTelTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.settings = cls.env['connect.settings'].sudo()
        cls.settings.set_param('voicetel_account_sid', 'AC' + '1' * 32)
        cls.settings.set_param('voicetel_api_key', 'k' * 64)
        cls.settings.set_param('voicetel_api_host', 'voiceml.voicetel.com')
        cls.env['ir.config_parameter'].sudo().set_param(
            'connect.api_url', 'https://odoo.test/')
        cls.env['ir.config_parameter'].sudo().set_param(
            'web.base.url', 'https://odoo.test/')

    def test_the_client_targets_the_configured_host_with_the_account(self):
        client = self.settings.get_voicetel_client()

        self.assertIsInstance(client, Client)
        self.assertEqual(client.account_sid, 'AC' + '1' * 32)
        self.assertEqual(client.base_url, 'https://voiceml.voicetel.com')

    def test_the_host_setting_is_normalized(self):
        self.settings.set_param('voicetel_api_host', ' VoiceML.Example.NET/ ')

        self.assertEqual(self.settings._voicetel_api_host(), 'voiceml.example.net')
        client = self.settings.get_voicetel_client()
        self.assertEqual(client.base_url, 'https://voiceml.example.net')

    def test_callback_urls_carry_no_fragment(self):
        url = self.settings.voicetel_webhook_url('voicetel/webhook/callstatus')

        self.assertEqual(url, 'https://odoo.test/voicetel/webhook/callstatus')

    def test_phone_settings_payload(self):
        self.settings.set_param('voicetel_stun_server', 'stun:stun.example.com')

        payload = self.settings.voicetel_get_phone_settings()

        self.assertTrue(payload['phone_enabled'])
        self.assertEqual(payload['user_agent']['phone_sip_protocol'], 'wss')
        self.assertEqual(
            payload['user_agent']['phone_stun_server'], 'stun:stun.example.com')
