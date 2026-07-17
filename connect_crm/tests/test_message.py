from types import SimpleNamespace

from odoo.tests import tagged

from .common import ConnectCrmTestCommon


@tagged('post_install', '-at_install', 'connect_crm_message')
class TestLeadFromMessage(ConnectCrmTestCommon):

    def test_create_record_from_message_reuses_existing_lead(self):
        existing = self._create_lead(name='Existing', phone='+380672323233')
        msg = SimpleNamespace(from_number='+380672323233')
        lead = self.Lead.create_record_from_message(msg)
        self.assertEqual(lead, existing)

    def test_create_record_from_message_creates_new_with_defaults(self):
        msg = SimpleNamespace(from_number='+380672424244')
        lead = self.Lead.create_record_from_message(
            msg, default_values={'description': 'from SMS'})
        self.assertTrue(lead.id)
        self.assertEqual(lead.phone, '+380672424244')
        self.assertEqual(lead.name, '+380672424244')
        self.assertIn('from SMS', lead.description or '')

    def test_summary_posted_to_lead_when_setting_enabled(self):
        self.Settings.set_param('register_summary', True)
        lead = self._create_lead(name='Summary', phone='+380672525255')
        call = self._create_call(caller='+380672525255', lead=lead.id)
        with self.mock_reload_view():
            call.summary = 'Customer wants a callback tomorrow.'
        messages = self.env['mail.message'].search(
            [('model', '=', 'crm.lead'), ('res_id', '=', lead.id)],
            order='id desc')
        self.assertTrue(
            any('callback' in (m.body or '') for m in messages),
            'Summary must be posted to lead chatter')

    def test_summary_not_posted_when_setting_disabled(self):
        self.Settings.set_param('register_summary', False)
        lead = self._create_lead(name='NoSummary', phone='+380672626266')
        call = self._create_call(caller='+380672626266', lead=lead.id)
        before = self.env['mail.message'].search_count(
            [('model', '=', 'crm.lead'), ('res_id', '=', lead.id)])
        call.summary = 'Should not be posted.'
        after = self.env['mail.message'].search_count(
            [('model', '=', 'crm.lead'), ('res_id', '=', lead.id)])
        self.assertEqual(before, after)
