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
        cls.sender.user.group_ids |= cls.env.ref('connect.group_admin')
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

    def test_whatsapp_sender_sync_reads_every_page_before_deleting(self):
        second = self.env['connect.telnyx.whatsapp_sender'].create({
            'number': '+15550000002',
            'phone_number_id': 'phone-2',
        })
        requested_pages = []

        def api_response(_self, method, path, **kwargs):
            self.assertEqual((method, path), (
                'GET', 'whatsapp/phone_numbers'))
            page = kwargs['params']['page[number]']
            requested_pages.append(page)
            items = [{
                'phone_number': '+15550000001',
                'phone_number_id': 'phone-1',
            }] if page == 1 else [{
                'phone_number': second.number,
                'phone_number_id': second.phone_number_id,
            }]
            return {
                'data': items,
                'meta': {
                    'page_number': page,
                    'total_pages': 2,
                    'total_results': 2,
                },
            }

        sender_model = type(self.env['connect.telnyx.whatsapp_sender'])
        with patch.object(Settings, 'telnyx_api_request', autospec=True,
                          side_effect=api_response), patch.object(
                              sender_model, '_fetch_profile', autospec=True,
                              return_value=None):
            self.env['connect.telnyx.whatsapp_sender'].sync()

        self.assertEqual(requested_pages, [1, 2])
        self.assertTrue(second.exists())

    def test_whatsapp_template_sync_reads_every_page_before_deleting(self):
        second = self.env['connect.telnyx.whatsapp_template'].create({
            'name': 'page_two',
            'language': 'en',
            'category': 'UTILITY',
            'telnyx_id': 'template-2',
            'status': 'APPROVED',
        })
        requested_pages = []

        def item(template_id, name):
            return {
                'id': template_id,
                'name': name,
                'language': 'en',
                'category': 'UTILITY',
                'status': 'APPROVED',
                'components': [],
            }

        def api_response(_self, method, path, **kwargs):
            self.assertEqual((method, path), (
                'GET', 'whatsapp/message_templates'))
            page = kwargs['params']['page[number]']
            requested_pages.append(page)
            items = [item('template-1', 'page_one')] if page == 1 else [
                item(second.telnyx_id, second.name)]
            return {
                'data': items,
                'meta': {
                    'page_number': page,
                    'total_pages': 2,
                    'total_results': 2,
                },
            }

        with patch.object(Settings, 'telnyx_api_request', autospec=True,
                          side_effect=api_response):
            self.env['connect.telnyx.whatsapp_template'].sync()

        self.assertEqual(requested_pages, [1, 2])
        self.assertTrue(second.exists())

    def test_malformed_whatsapp_collection_never_deletes_local_records(self):
        template = self.env['connect.telnyx.whatsapp_template'].create({
            'name': 'keep_on_error',
            'language': 'en',
            'category': 'UTILITY',
            'telnyx_id': 'template-keep',
            'status': 'APPROVED',
        })
        with patch.object(Settings, 'telnyx_api_request', autospec=True,
                          return_value={}):
            with self.assertRaises(ValidationError):
                self.env['connect.telnyx.whatsapp_template'].sync()
        self.assertTrue(template.exists())

    def test_incomplete_whatsapp_collection_never_deletes_local_records(self):
        template = self.env['connect.telnyx.whatsapp_template'].create({
            'name': 'keep_on_partial_page',
            'language': 'en',
            'category': 'UTILITY',
            'telnyx_id': 'template-partial',
            'status': 'APPROVED',
        })

        def api_response(_self, method, path, **kwargs):
            page = kwargs['params']['page[number]']
            return {
                'data': [{
                    'id': 'template-other',
                    'name': 'other',
                    'language': 'en',
                    'category': 'UTILITY',
                    'status': 'APPROVED',
                    'components': [],
                }] if page == 1 else [],
                'meta': {
                    'page_number': page,
                    'total_pages': 2,
                    'total_results': 2,
                },
            }

        with patch.object(Settings, 'telnyx_api_request', autospec=True,
                          side_effect=api_response):
            with self.assertRaises(ValidationError):
                self.env['connect.telnyx.whatsapp_template'].sync()
        self.assertTrue(template.exists())

    def test_no_sync_sender_is_not_deleted_when_remote_is_empty(self):
        sender = self.env['connect.telnyx.whatsapp_sender'].create({
            'number': '+15550000003',
            'phone_number_id': 'phone-3',
            'no_sync': True,
        })
        with patch.object(Settings, 'telnyx_api_request', autospec=True,
                          return_value={
                              'data': [],
                              'meta': {'page_number': 1, 'total_pages': 1},
                          }):
            self.env['connect.telnyx.whatsapp_sender'].sync()
        self.assertTrue(sender.exists())
