# -*- coding: utf-8 -*-
"""connect.settings 3CX extension: API key handling, CRM template
rendering and the click-to-call dispatcher override."""
import xml.dom.minidom

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import ThreeCXTestCommon, API_KEY, PBX_URL, ODOO_URL


@tagged('post_install', '-at_install', 'connect_3cx')
class TestThreeCXSettings(ThreeCXTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.settings_rec = cls.Settings.search([], limit=1)

    def test_api_key_validation(self):
        with self.assertRaises(ValidationError):
            self.settings_rec.write({'display_threecx_api_key': 'short'})
        with self.assertRaises(ValidationError):
            self.settings_rec.write(
                {'display_threecx_api_key': 'x' * 30 + '!!'})

    def test_generate_api_key(self):
        self.settings_rec.threecx_generate_api_key()
        stored = self.Settings.get_param('threecx_api_key')
        self.assertNotEqual(stored, API_KEY)
        self.assertGreaterEqual(len(stored), 24)
        # The display twin is masked back to asterisks by the core
        # protected-fields flow.
        self.assertTrue(set(self.settings_rec.display_threecx_api_key) == {'*'})

    def test_crm_template_render(self):
        xml_text = self.Settings.threecx_get_crm_template()
        # Placeholders substituted into the parameter defaults; the
        # request URLs reference the [OdooUrl] parameter.
        self.assertIn('Default="{}"'.format(ODOO_URL), xml_text)
        self.assertIn('Default="{}"'.format(API_KEY), xml_text)
        self.assertIn('[OdooUrl]/3cx/webhook/lookup', xml_text)
        self.assertIn('[OdooUrl]/3cx/webhook/report_call', xml_text)
        self.assertIn('[OdooUrl]/3cx/webhook/create_contact', xml_text)
        self.assertNotIn('$odoo_url', xml_text)
        self.assertNotIn('$api_key', xml_text)
        # Required scenarios present.
        self.assertIn('Id="ReportCall"', xml_text)
        self.assertIn('Id="CreateContactRecordFromClient"', xml_text)
        # Well-formed XML (minidom also rejects '--' inside comments,
        # which 3CX refuses as "incorrect file format").
        dom = xml.dom.minidom.parseString(xml_text)
        self.assertEqual(dom.documentElement.tagName, 'Crm')
        self.assertEqual(
            dom.documentElement.getAttribute('Name'), 'Odoo Connect')

    def test_crm_template_requires_key(self):
        self.Settings.set_param('threecx_api_key', False)
        with self.assertRaises(ValidationError):
            self.Settings.threecx_get_crm_template()

    def test_download_template_generates_missing_key(self):
        self.Settings.set_param('threecx_api_key', False)
        action = self.settings_rec.threecx_download_template()
        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertEqual(action['url'], '/3cx/template')
        self.assertTrue(self.Settings.get_param('threecx_api_key'))

    def test_originate_returns_dial_url_action(self):
        action = self.Settings.with_user(self.odoo_user).originate_call(
            '+1 555 123-4567')
        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertEqual(action['target'], 'new')
        self.assertEqual(
            action['url'],
            '{}/webclient/#/call?phone=%2B15551234567'.format(PBX_URL))

    def test_originate_requires_configuration(self):
        self.Settings.set_param('threecx_enabled', False)
        with self.assertRaises(ValidationError):
            self.Settings.with_user(self.odoo_user).originate_call(
                '+15551234567')

    def test_originate_requires_number(self):
        with self.assertRaises(ValidationError):
            self.Settings.with_user(self.odoo_user).originate_call('  ')

    def test_pbx_number_fields(self):
        self.assertIn(
            'threecx_exten', self.env['connect.user']._pbx_number_fields())
        self.assertEqual(self.connect_user.get_pbx_number(), '101')
