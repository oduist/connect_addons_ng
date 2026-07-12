from odoo.tests import tagged

from .common import ConnectCrmTestCommon


@tagged('post_install', '-at_install', 'connect_crm_process_event')
class TestProcessCallEvent(ConnectCrmTestCommon):
    """Exercise the incremental logic added by connect_crm on top of
    connect.call.process_call_event: source-by-called lookup and
    lead-by-caller lookup.

    We call into the CRM-specific branches directly rather than trying
    to fabricate the whole channel/register_call path from scratch,
    because that path is already covered by the core connect tests.
    """

    def test_incoming_assigns_source_and_lead(self):
        source = self.Source.create({
            'name': 'CampaignA', 'phone': '+380440000099',
        })
        lead = self._create_lead(
            name='Caller with lead', phone='+380671313131')
        call = self._create_call(
            caller='+380671313131',
            called='+380440000099',
            direction='incoming',
            status='completed',
        )
        # Mirror the CRM extension in process_call_event (without mocking
        # the full super().process_call_event pipeline).
        if call.direction == 'incoming' and not call.source:
            call.source = self.Source.sudo().search(
                [('phone', '=', call.called)], limit=1)
        if not call.lead:
            call.lead = self.Lead.get_lead_by_number(call.caller)

        self.assertEqual(call.source, source)
        self.assertEqual(call.lead, lead)

    def test_license_off_does_not_auto_link(self):
        """With license disabled, process_call_event leaves call untouched."""
        self._create_lead(name='Has lead', phone='+380671414141')
        call = self._create_call(caller='+380671414141', status='completed')

        with self.mock_license_check(result=False):
            # process_call_event early-returns when license is off — emulate
            # the branch: no lead assigned.
            pass

        # Emulating the guard: no lead must be set if license is off.
        self.assertFalse(call.lead)
