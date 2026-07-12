from odoo.tests import tagged

from .common import ConnectCrmTestCommon


@tagged('post_install', '-at_install', 'connect_crm_actions')
class TestCallActions(ConnectCrmTestCommon):

    def test_create_lead_button_for_incoming_sets_default_phone_caller(self):
        call = self._create_call(
            caller='+380671515151',
            called='100',
            direction='incoming',
        )
        action = call.create_lead_button()
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'crm.lead')
        self.assertEqual(action['view_mode'], 'form')
        self.assertEqual(action['context']['default_phone'], '+380671515151')
        self.assertEqual(action['context']['connect_call_id'], call.id)

    def test_create_lead_button_for_outgoing_sets_default_phone_called(self):
        call = self._create_call(
            caller='200',
            called='+380671616161',
            direction='outgoing',
        )
        action = call.create_lead_button()
        self.assertEqual(action['context']['default_phone'], '+380671616161')

    def test_create_lead_button_reuses_existing_lead_by_number(self):
        existing = self._create_lead(name='Existing', phone='+380671717171')
        call = self._create_call(caller='+380671717171')
        action = call.create_lead_button()
        call.invalidate_recordset(['lead'])
        self.assertEqual(call.lead, existing)
        self.assertEqual(action['res_id'], existing.id)

    def test_create_lead_button_returns_empty_res_id_when_no_lead(self):
        call = self._create_call(caller='+380671818181')
        action = call.create_lead_button()
        self.assertFalse(action['res_id'])

    def test_unlink_crm_lead_clears_link(self):
        lead = self._create_lead(name='L1', phone='+380671919191')
        call = self._create_call(caller='+380671919191', lead=lead.id)
        self.assertEqual(call.lead, lead)
        call.unlink_crm_lead()
        self.assertFalse(call.lead)

    def test_get_ref_returns_lead_reference(self):
        lead = self._create_lead(name='L2', phone='+380672020202')
        call = self._create_call(caller='+380672020202', lead=lead.id)
        call._get_ref()
        self.assertTrue(call.ref)
        self.assertEqual(call.ref._name, 'crm.lead')
        self.assertEqual(call.ref.id, lead.id)

    def test_get_ref_falls_back_to_partner_when_no_lead(self):
        call = self._create_call(caller='+380672121212', partner=self.partner.id)
        call._get_ref()
        # Partner fallback comes from the core connect.call._get_ref
        self.assertTrue(call.ref)
        self.assertEqual(call.ref._name, 'res.partner')
        self.assertEqual(call.ref.id, self.partner.id)

    def test_get_widget_fields_includes_lead(self):
        self.assertIn('lead', self.Call.get_widget_fields())

    def test_connect_calls_count_is_stored_and_updates(self):
        lead = self._create_lead(name='Stats', phone='+380672222222')
        self._create_call(caller='+380672222222', lead=lead.id)
        self._create_call(caller='+380672222222', lead=lead.id)
        lead.invalidate_recordset(['connect_calls', 'connect_calls_count'])
        self.assertEqual(len(lead.connect_calls), 2)
        self.assertEqual(lead.connect_calls_count, 2)
