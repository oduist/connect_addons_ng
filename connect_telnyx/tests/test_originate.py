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

    def _originate(self, captured, **kwargs):
        """Run originate_call, capturing the TeXML calls request."""

        def api_response(_self, method, path, payload=None, **kw):
            if path == 'whoami':
                return {'data': {'organization_id': 'org-resolved'}}
            captured['method'] = method
            captured['path'] = path
            captured.update(payload or {})
            return {'sid': 'call-sid-test', 'status': 'queued'}

        with patch.object(Settings, 'get_telnyx_client', autospec=True,
                          return_value=object()), patch.object(
                              Settings, 'telnyx_api_request', autospec=True,
                              side_effect=api_response):
            self.env['connect.settings'].originate_call(
                '+15559998888', user=self.caller.user, **kwargs)

    def test_originate_sends_the_application_sid(self):
        captured = {}
        self._originate(captured)
        self.assertEqual(captured['method'], 'POST')
        self.assertEqual(captured['path'], 'texml/Accounts/account-test/Calls')
        self.assertEqual(captured['ApplicationSid'], 'number-app-sid')
        self.assertEqual(captured['From'], '+15550001234')
        self.assertIn('client-telnyx_originate', captured['To'])
        channel = self.env['connect.channel'].search(
            [('sid', '=', 'call-sid-test')])
        self.assertEqual(len(channel), 1)
        self.assertEqual(channel.called, '+15559998888')

    def test_originate_omits_empty_custom_headers(self):
        """Telnyx rejects an X- header with an empty value."""
        captured = {}
        self._originate(captured)
        self.assertNotIn('=&', captured['To'])
        self.assertFalse(captured['To'].endswith('='))
        self.assertIn('X-autoAnswer=yes', captured['To'])
        self.assertNotIn('X-Partner', captured['To'])

    def test_originate_keeps_custom_headers_that_have_a_value(self):
        captured = {}
        partner = self.env['res.partner'].create({'name': 'Callee'})
        self._originate(
            captured, res_model='res.partner', res_id=partner.id)
        self.assertIn('X-Partner={}'.format(partner.id), captured['To'])
        self.assertIn('X-CallerName=Callee', captured['To'])
        self.assertNotIn('=&', captured['To'])

    def test_originate_resolves_a_missing_account_sid(self):
        self.settings.set_param('telnyx_account_sid', False)
        captured = {}
        self._originate(captured)
        self.assertEqual(captured['path'], 'texml/Accounts/org-resolved/Calls')
