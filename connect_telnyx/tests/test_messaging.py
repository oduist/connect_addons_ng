# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.connect_telnyx.models.settings import Settings

from .common import TelnyxTestCommon


@tagged('post_install', '-at_install')
class TestTelnyxMessaging(TelnyxTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.settings = cls.env['connect.settings'].sudo()
        cls.settings.set_param('telnyx_auto_sync', False)
        # The sending user must resolve to the Telnyx messaging provider
        # even when another provider module is installed alongside.
        cls.sender = cls._create_connect_user(
            'telnyx_messaging', message_provider='telnyx')
        cls.sender.user.groups_id |= cls.env.ref('connect.group_admin')
        cls.env = cls.env(user=cls.sender.user)
        cls.callerid = cls.env['connect.telnyx.outgoing_callerid'].create({
            'number': '+15550005555',
            'friendly_name': 'Default sender',
            'is_default': True,
        })

    def test_send_falls_back_to_the_default_caller_id(self):
        captured = {}

        def client_send(_self, recipient, sender, body):
            captured['sender'] = sender
            return type('Msg', (), {'id': 'msg-1', 'errors': [], 'media': []})()

        with patch.object(
                type(self.env['connect.message']), 'telnyx_client_send',
                autospec=True, side_effect=client_send):
            self.env['connect.message'].send('+15550006666', 'Hello')
        self.assertEqual(captured['sender'], self.callerid.number)

    def test_send_surfaces_the_provider_error(self):
        error = Exception(
            "Error code: 400 - {'errors': [{'code': '40305', 'title': "
            "\"Invalid 'from' address\"}]}")

        class Messages:
            @staticmethod
            def send(**kwargs):
                raise error

        class Client:
            messages = Messages()

        with patch.object(Settings, 'get_telnyx_client', autospec=True,
                          return_value=Client()):
            with self.assertRaises(ValidationError) as cm:
                self.env['connect.message'].send('+15550006666', 'Hello')
        self.assertIn("Invalid 'from' address", str(cm.exception))

    def test_whatsapp_endpoints_are_not_double_prefixed(self):
        """The SDK WhatsApp resources prefix their paths with /v2 while the
        client base URL already ends in /v2, so those calls go through the
        settings helper with a plain relative path."""
        calls = []

        def api_response(_self, method, path, **kwargs):
            calls.append(path)
            return {'data': []}

        with patch.object(Settings, 'telnyx_api_request', autospec=True,
                          side_effect=api_response):
            self.env['connect.telnyx.whatsapp_sender'].sync()
            self.env['connect.telnyx.whatsapp_template'].sync()
        self.assertEqual(
            calls, ['whatsapp/phone_numbers', 'whatsapp/message_templates'])
        for path in calls:
            self.assertFalse(path.startswith('/v2'))
            self.assertNotIn('v2/v2', path)

    def test_whatsapp_send_uses_an_existing_sdk_method(self):
        from telnyx import Telnyx
        client = Telnyx(api_key='test-key')
        self.assertTrue(
            hasattr(client.messages, 'whatsapp'),
            'The Telnyx SDK no longer exposes messages.whatsapp')
