from odoo.tests import tagged

from .common import ConnectCrmTestCommon


@tagged('post_install', '-at_install')
class TestLeadCallOrigin(ConnectCrmTestCommon):
    """A call started from a lead reaches the lead and its contact once."""

    def test_lead_origin_and_link_are_deduplicated(self):
        self.Settings.set_param('register_summary', True)
        partner = self.env['res.partner'].create({'name': 'Lead Contact'})
        lead = self._create_lead(
            name='Origin Lead', phone='+441865600008', partner_id=partner.id)
        call = self._create_call(
            called='+441865600008', direction='outgoing', lead=lead.id,
            partner=partner.id, origin_model='crm.lead', origin_res_id=lead.id)
        self.assertEqual(call._get_registration_records(), [lead, partner])
        with self.mock_reload_view():
            call.summary = '<p>Mark will call back tomorrow.</p>'
        for record in (lead, partner):
            posted = self.env['mail.message'].search([
                ('model', '=', record._name), ('res_id', '=', record.id),
                ('body', 'ilike', 'call back tomorrow'),
            ])
            self.assertEqual(len(posted), 1, record._name)
