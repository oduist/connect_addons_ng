from odoo.tests import tagged

from .common import ConnectCrmTestCommon


@tagged('post_install', '-at_install', 'connect_crm_lookup')
class TestLeadLookup(ConnectCrmTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.lead_plus = cls._create_lead(
            name='Plus-prefixed', phone='+380671234567')
        cls.lead_bare = cls._create_lead(
            name='Bare number', phone='380507654321')
        cls.lead_mobile = cls._create_lead(
            name='Mobile only', mobile='+14155550123')

    def test_lookup_with_plus_prefix(self):
        found = self.Lead.get_lead_by_number('+380671234567')
        self.assertEqual(found, self.lead_plus)

    def test_lookup_without_plus(self):
        found = self.Lead.get_lead_by_number('380507654321')
        self.assertEqual(found, self.lead_bare)

    def test_lookup_by_mobile_field(self):
        found = self.Lead.get_lead_by_number('+14155550123')
        self.assertEqual(found, self.lead_mobile)

    def test_lookup_missing_returns_empty(self):
        found = self.Lead.get_lead_by_number('+999999999999')
        self.assertFalse(found)

    def test_lookup_short_number_skipped(self):
        self.assertFalse(self.Lead.get_lead_by_number('1234'))

    def test_lookup_empty_or_unknown_skipped(self):
        self.assertFalse(self.Lead.get_lead_by_number(''))
        self.assertFalse(self.Lead.get_lead_by_number('unknown'))
        self.assertFalse(self.Lead.get_lead_by_number('s'))

    def test_lookup_ignores_won_stages(self):
        """Won leads must not be returned by number lookup."""
        won = self.env['crm.stage'].search([('is_won', '=', True)], limit=1)
        if not won:
            self.skipTest('No won stage in this env')
        self.lead_plus.stage_id = won
        found = self.Lead.get_lead_by_number('+380671234567')
        self.assertFalse(found, 'Won lead should be excluded')
