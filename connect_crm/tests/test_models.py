from psycopg2 import IntegrityError

from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import ConnectCrmTestCommon


@tagged('post_install', '-at_install', 'connect_crm_models')
class TestModels(ConnectCrmTestCommon):

    def test_connect_call_added_fields(self):
        fields = self.Call._fields
        self.assertEqual(fields['lead'].type, 'many2one')
        self.assertEqual(fields['lead'].comodel_name, 'crm.lead')
        self.assertEqual(fields['source'].type, 'many2one')
        self.assertEqual(fields['source'].comodel_name, 'utm.source')
        self.assertEqual(fields['ref'].type, 'reference')

    def test_ref_selection_includes_crm_lead(self):
        sel = dict(self.Call._fields['ref']._description_selection(self.env))
        self.assertIn('crm.lead', sel)

    def test_crm_lead_added_fields(self):
        lf = self.Lead._fields
        self.assertEqual(lf['connect_calls'].type, 'one2many')
        self.assertEqual(lf['connect_calls'].comodel_name, 'connect.call')
        self.assertEqual(lf['connect_calls_count'].type, 'integer')
        self.assertEqual(lf['mobile'].type, 'char')
        self.assertEqual(lf['phone_normalized'].type, 'char')
        self.assertEqual(lf['mobile_normalized'].type, 'char')

    def test_settings_autocreate_fields(self):
        expected = {
            'auto_create_leads_for_in_calls',
            'auto_create_leads_for_in_answered_calls',
            'auto_create_leads_for_in_missed_calls',
            'auto_create_leads_for_in_unknown_callers',
            'auto_create_leads_for_out_calls',
            'auto_create_leads_for_out_answered_calls',
            'auto_create_leads_for_out_missed_calls',
            'auto_create_leads_sales_person',
            'auto_create_leads_type',
        }
        missing = expected - set(self.env['connect.settings']._fields)
        self.assertFalse(missing, 'Missing settings fields: %s' % missing)

    def test_message_configuration_destination_has_lead(self):
        # The extension moved to the auto-installed connect_crm_twilio
        # bridge; the model only exists when connect_twilio is installed.
        if 'connect.twilio.message_configuration' not in self.env:
            self.skipTest('connect_twilio / connect_crm_twilio not installed')
        MC = self.env['connect.twilio.message_configuration']
        sel = dict(MC._fields['destination']._description_selection(self.env))
        self.assertIn('crm.lead', sel)

    def test_utm_source_phone_field_present(self):
        self.assertIn('phone', self.Source._fields)

    def test_utm_source_phone_unique_on_insert(self):
        self.Source.create({'name': 'SrcA', 'phone': '+380440000011'})
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.Source.create({'name': 'SrcB', 'phone': '+380440000011'})
                self.env.flush_all()

    def test_utm_source_phone_unique_on_update(self):
        self.Source.create({'name': 'SrcA', 'phone': '+380440000021'})
        other = self.Source.create({'name': 'SrcB', 'phone': '+380440000022'})
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                other.phone = '+380440000021'
                self.env.flush_all()

    def test_phone_normalized_compute(self):
        lead = self._create_lead(phone='+380671234567', mobile='+14155550123')
        self.env.flush_all()
        self.assertEqual(lead.phone_normalized, '+380671234567')
        self.assertEqual(lead.mobile_normalized, '+14155550123')

    def test_phone_normalized_cleared_when_empty(self):
        lead = self._create_lead(phone='+380671234567')
        lead.phone = False
        lead.invalidate_recordset(['phone_normalized'])
        self.assertFalse(lead.phone_normalized)
