# -*- coding: utf-8 -*-
"""connect.settings Asterisk extension tests."""
from odoo.exceptions import ValidationError
from odoo.tests import tagged, new_test_user

from .common import AsteriskTestCommon, AGENT_TOKEN


@tagged('post_install', '-at_install', 'connect_asterisk')
class TestAsteriskSettings(AsteriskTestCommon):

    def test_token_validation_too_short(self):
        with self.assertRaises(ValidationError):
            self.Settings.set_param(
                'display_asterisk_agent_token', 'short')

    def test_token_validation_bad_chars(self):
        with self.assertRaises(ValidationError):
            self.Settings.set_param(
                'display_asterisk_agent_token', 'x' * 30 + '!@#$')

    def test_token_masked_after_write(self):
        token = 'a' * 32
        self.Settings.set_param('display_asterisk_agent_token', token)
        self.assertEqual(self.Settings.get_param('asterisk_agent_token'),
                         token)
        self.assertEqual(
            self.Settings.get_param('display_asterisk_agent_token'),
            '*' * len(token))

    def test_token_hidden_from_non_admin(self):
        # asterisk_agent_token carries groups="connect.group_admin":
        # get_param must not leak it to a plain internal user.
        plain = new_test_user(
            self.env, login='ast_plain', groups='base.group_user')
        value = self.Settings.with_user(plain).get_param(
            'asterisk_agent_token')
        self.assertFalse(value)

    def test_agent_config_payload(self):
        self.Settings.set_param('asterisk_ami_host', '10.0.0.5')
        self.Settings.set_param('asterisk_ami_user', 'connect-agent')
        self.Settings.set_param('asterisk_ami_password', 'secret-ami')
        config = self.Settings.asterisk_get_agent_config()
        self.assertEqual(config['ami']['host'], '10.0.0.5')
        self.assertEqual(config['ami']['port'], 5038)
        self.assertEqual(config['ami']['user'], 'connect-agent')
        self.assertEqual(config['ami']['password'], 'secret-ami')
        self.assertIn('Newchannel', config['events'])
        self.assertIn('Hangup', config['events'])
        self.assertTrue(config['recordings_enabled'])

    def test_phone_settings_gated_on_enabled(self):
        self.Settings.set_param('asterisk_phone_enabled', True)
        self.Settings.set_param('asterisk_enabled', False)
        self.assertFalse(
            self.Settings.asterisk_get_phone_settings()['phone_enabled'])
        self.Settings.set_param('asterisk_enabled', True)
        self.Settings.set_param(
            'asterisk_websocket_url', 'wss://pbx.example.com:8089/ws')
        settings = self.Settings.asterisk_get_phone_settings()
        self.assertTrue(settings['phone_enabled'])
        agent = settings['user_agent']
        self.assertEqual(agent['phone_websocket'],
                         'wss://pbx.example.com:8089/ws')
        # SIP proxy falls back to the WebSocket host.
        self.assertEqual(agent['phone_sip_proxy'], 'pbx.example.com')
        self.assertEqual(agent['phone_sip_protocol'], 'wss')
        self.assertTrue(agent['phone_realm'])
        self.assertTrue(agent['phone_stun_server'])

    def test_agent_request_without_url_raises(self):
        self.Settings.set_param('asterisk_agent_url', False)
        with self.assertRaises(ValidationError):
            self.Settings.asterisk_agent_request('/ami_action', {})
        self.assertFalse(self.Settings.asterisk_agent_request(
            '/ami_action', {}, raise_exc=False))
