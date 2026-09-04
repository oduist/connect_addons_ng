from odoo.tests import tagged

from .common import ConnectCrmTestCommon


@tagged('post_install', '-at_install', 'connect_crm_autocreate')
class TestAutoCreateLead(ConnectCrmTestCommon):

    def test_incoming_answered_unknown_caller_creates_lead(self):
        self._set_autocreate_flags(
            auto_create_leads_for_in_calls=True,
            auto_create_leads_for_in_unknown_callers=True,
        )
        call = self._create_call(caller='+380670000001', status='completed')
        self.assertTrue(call._auto_create_lead())
        self.assertTrue(call.lead)
        self.assertEqual(call.lead.type, 'lead')
        self.assertEqual(call.lead.phone, '+380670000001')

    def test_incoming_known_caller_skips_unknown_rule(self):
        # The unknown-callers rule must not fire for known contacts.
        self._set_autocreate_flags(
            auto_create_leads_for_in_calls=True,
            auto_create_leads_for_in_answered_calls=False,
            auto_create_leads_for_in_missed_calls=False,
            auto_create_leads_for_in_unknown_callers=True,
        )
        call = self._create_call(
            caller='+380671010101', status='completed',
            partner=self.partner.id,
        )
        self.assertFalse(call._auto_create_lead())
        self.assertFalse(call.lead)

    def test_incoming_missed_creates_lead(self):
        self._set_autocreate_flags(
            auto_create_leads_for_in_calls=True,
            auto_create_leads_for_in_unknown_callers=True,
        )
        call = self._create_call(caller='+380670000002', status='missed')
        call._auto_create_lead()
        self.assertTrue(call.lead)

    def test_incoming_answered_settings_off_skip(self):
        self._set_autocreate_flags(
            auto_create_leads_for_in_calls=True,
            auto_create_leads_for_in_answered_calls=False,
            auto_create_leads_for_in_missed_calls=False,
            auto_create_leads_for_in_unknown_callers=False,
        )
        call = self._create_call(caller='+380670000003', status='completed')
        self.assertFalse(call._auto_create_lead())
        self.assertFalse(call.lead)

    def test_incoming_master_flag_off_skips(self):
        self._set_autocreate_flags(auto_create_leads_for_in_calls=False)
        call = self._create_call(caller='+380670000004', status='completed')
        self.assertFalse(call._auto_create_lead())
        self.assertFalse(call.lead)

    def test_outgoing_answered_creates_lead(self):
        self._set_autocreate_flags(auto_create_leads_for_out_calls=True)
        call = self._create_call(
            caller='+380440000010',
            called='+380670000010',
            direction='outgoing',
            status='completed',
        )
        call._auto_create_lead()
        self.assertTrue(call.lead)
        self.assertEqual(call.lead.phone, '+380670000010')

    def test_outgoing_missed_creates_lead(self):
        self._set_autocreate_flags(auto_create_leads_for_out_calls=True)
        call = self._create_call(
            caller='+380440000011',
            called='+380670000011',
            direction='outgoing',
            status='no answer',
        )
        call._auto_create_lead()
        self.assertTrue(call.lead)

    def test_outgoing_master_flag_off_skips(self):
        self._set_autocreate_flags(auto_create_leads_for_out_calls=False)
        call = self._create_call(
            caller='+380440000012',
            called='+380670000012',
            direction='outgoing',
            status='completed',
        )
        self.assertFalse(call._auto_create_lead())
        self.assertFalse(call.lead)

    def test_already_linked_call_is_skipped(self):
        self._set_autocreate_flags(
            auto_create_leads_for_in_calls=True,
            auto_create_leads_for_in_unknown_callers=True,
        )
        prelead = self._create_lead(name='Pre', phone='+380670000020')
        call = self._create_call(caller='+380670000020', lead=prelead.id)
        self.assertFalse(call._auto_create_lead())
        self.assertEqual(call.lead, prelead)

    def test_opportunity_type(self):
        self._set_autocreate_flags(
            auto_create_leads_for_in_calls=True,
            auto_create_leads_for_in_unknown_callers=True,
            auto_create_leads_type='opportunity',
        )
        call = self._create_call(caller='+380670000030', status='completed')
        call._auto_create_lead()
        self.assertEqual(call.lead.type, 'opportunity')

    def test_fallback_salesperson_used_when_no_pbx_user(self):
        self._set_autocreate_flags(
            auto_create_leads_for_in_calls=True,
            auto_create_leads_for_in_unknown_callers=True,
        )
        call = self._create_call(caller='+380670000040', status='completed')
        call._auto_create_lead()
        self.assertEqual(call.lead.user_id, self.salesperson)
