# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.connect_telnyx.models.settings import Settings

from .common import TelnyxTestCommon


@tagged('post_install', '-at_install')
class TestTelnyxOriginate(TelnyxTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.settings = cls.env['connect.settings'].sudo()
        cls.settings.set_param('telnyx_auto_sync', False)
        cls.settings.set_param('telnyx_account_sid', 'account-test')
        cls.env['connect.telnyx.number'].get_number_app().with_context(
            skip_telnyx_sync=True).write({'sid': 'number-app-sid'})
        cls.env['connect.telnyx.outgoing_callerid'].create({
            'number': '+15550001234',
            'friendly_name': 'Default',
            'is_default': True,
        })
        cls.caller = cls._create_web_phone_user(
            'telnyx_originate', originate_provider='telnyx')

    def _client(self, captured):
        class Calls:
            @staticmethod
            def calls(account_sid, **kwargs):
                captured['account_sid'] = account_sid
                captured.update(kwargs)
                return type('Call', (), {'sid': 'call-sid-test'})()

        class Accounts:
            calls = Calls()

        class Texml:
            accounts = Accounts()

        class Client:
            texml = Texml()

        return Client()

    def test_originate_sends_the_application_sid(self):
        captured = {}
        with patch.object(Settings, 'get_telnyx_client', autospec=True,
                          return_value=self._client(captured)):
            self.env['connect.settings'].originate_call(
                '+15559998888', user=self.caller.user)
        self.assertEqual(captured['account_sid'], 'account-test')
        self.assertEqual(captured['application_sid'], 'number-app-sid')
        self.assertEqual(captured['from_'], '+15550001234')
        self.assertIn('client-telnyx_originate', captured['to'])
        channel = self.env['connect.channel'].search(
            [('sid', '=', 'call-sid-test')])
        self.assertEqual(len(channel), 1)
        self.assertEqual(channel.called, '+15559998888')

    def test_originate_resolves_a_missing_account_sid(self):
        self.settings.set_param('telnyx_account_sid', False)
        captured = {}

        def api_response(_self, method, path, **kwargs):
            return {'data': {'organization_id': 'org-resolved'}}

        with patch.object(Settings, 'get_telnyx_client', autospec=True,
                          return_value=self._client(captured)), patch.object(
                              Settings, 'telnyx_api_request', autospec=True,
                              side_effect=api_response):
            self.env['connect.settings'].originate_call(
                '+15559998888', user=self.caller.user)
        self.assertEqual(captured['account_sid'], 'org-resolved')
