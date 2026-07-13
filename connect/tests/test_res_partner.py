from odoo.tests import tagged

from .common import ConnectTestCommon


@tagged('at_install', '-post_install')
class TestResPartner(ConnectTestCommon):

    def test_get_partner_by_number_found(self):
        """Test partner found by phone number."""
        partner = self.env['res.partner'].get_partner_by_number('+15551234567')
        self.assertTrue(partner)
        self.assertEqual(partner.id, self.partner.id)

    def test_get_partner_by_number_not_found(self):
        """Test empty recordset for unknown number."""
        partner = self.env['res.partner'].get_partner_by_number('+19999999999')
        self.assertFalse(partner)

    def test_api_get_partner_found(self):
        """Test api_get_partner returns id and name."""
        result = self.env['res.partner'].api_get_partner('+15551234567')
        self.assertEqual(result['id'], self.partner.id)
        self.assertIn('Test Partner', result['name'])

    def test_api_get_partner_not_found(self):
        """Test api_get_partner returns Unknown for missing partner."""
        result = self.env['res.partner'].api_get_partner('+19999999999')
        self.assertFalse(result['id'])
        self.assertEqual(result['name'], 'Unknown')

    def test_connect_calls_count_no_calls(self):
        """Test connect_calls_count is 0 with no calls."""
        self.assertEqual(self.partner.connect_calls_count, 0)

    def test_connect_calls_count_with_calls(self):
        """Test connect_calls_count increments with calls."""
        self._create_call(partner=self.partner.id)
        self.partner.invalidate_recordset()
        self.assertEqual(self.partner.connect_calls_count, 1)

    def test_connect_messages_count_no_messages(self):
        """Test connect_messages_count is 0 with no messages."""
        self.assertEqual(self.partner.connect_messages_count, 0)

    def test_connect_messages_count_with_messages(self):
        """Test connect_messages_count increments with messages."""
        self.env['connect.message'].create({
            'from_number': '+15551234567',
            'to_number': '+15552222222',
            'partner': self.partner.id,
            'status': 'received',
        })
        self.partner.invalidate_recordset()
        self.assertEqual(self.partner.connect_messages_count, 1)

    def test_connect_calls_count_company(self):
        """Test company partner counts include child contacts."""
        company = self.env['res.partner'].with_context(no_clear_cache=True).create({
            'name': 'Test Company',
            'is_company': True,
        })
        child = self.env['res.partner'].with_context(no_clear_cache=True).create({
            'name': 'Employee',
            'parent_id': company.id,
        })
        self._create_call(partner=child.id)
        company.invalidate_recordset()
        self.assertEqual(company.connect_calls_count, 1)

    def test_connect_user_compute(self):
        """Test connect_user computed from linked res.users."""
        connect_user = self._create_connect_user('partneruser', self.admin_user)
        self.admin_user.partner_id.invalidate_recordset()
        self.assertEqual(self.admin_user.partner_id.connect_user.id, connect_user.id)

    def test_create_partner_links_to_call(self):
        """Test creating partner with connect_call_id context links to call."""
        call = self._create_call()
        partner = self.env['res.partner'].with_context(
            connect_call_id=call.id, no_clear_cache=True,
        ).create({
            'name': 'New Partner',
            'phone': '+15558887777',
        })
        call.invalidate_recordset()
        self.assertEqual(call.partner.id, partner.id)

    def test_create_record_from_message(self):
        """Test create_record_from_message creates new partner."""
        msg = self.env['connect.message'].create({
            'from_number': '+15550009999',
            'to_number': '+15551111111',
            'status': 'received',
        })
        partner = self.env['res.partner'].create_record_from_message(msg)
        self.assertTrue(partner)
        self.assertEqual(partner.phone, '+15550009999')

    def test_create_record_from_message_existing(self):
        """Test create_record_from_message returns existing partner."""
        partner = self.env['res.partner'].create_record_from_message(
            self.env['connect.message'].create({
                'from_number': '+15551234567',
                'to_number': '+15552222222',
                'status': 'received',
            }),
        )
        self.assertEqual(partner.id, self.partner.id)

    def test_get_country(self):
        """Test _get_country returns country code."""
        country_us = self.env.ref('base.us')
        self.partner.country_id = country_us
        result = self.partner._get_country()
        self.assertEqual(result, 'US')

    def test_get_country_from_parent(self):
        """Test _get_country falls back to parent company country."""
        country_us = self.env.ref('base.us')
        company = self.env['res.partner'].with_context(no_clear_cache=True).create({
            'name': 'Parent Co',
            'is_company': True,
            'country_id': country_us.id,
        })
        child = self.env['res.partner'].with_context(no_clear_cache=True).create({
            'name': 'Child',
            'parent_id': company.id,
        })
        result = child._get_country()
        self.assertEqual(result, 'US')

    def test_normalize_phone(self):
        """Test _normalize_phone formats to E164."""
        self.partner.country_id = self.env.ref('base.us')
        result = self.partner._normalize_phone('+15551234567')
        self.assertTrue(result.startswith('+'))


@tagged('at_install', '-post_install')
class TestGetPartnerByNumberNormalization(ConnectTestCommon):
    """E.164 normalization fallback in get_partner_by_number (ADR-024).

    Providers deliver caller IDs in local format (0313808316) while the
    partner is stored in E.164 (+41313808316). get_partner_by_number
    retries with the number normalized against the main company's
    country when the literal search misses.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # get_partner_by_number normalizes against res.company.browse(1);
        # pin its country to CH so '0313808316' -> '+41313808316'.
        cls.env['res.company'].browse(1).country_id = cls.env.ref('base.ch')
        cls.swiss_partner = cls.env['res.partner'].with_context(
            no_clear_cache=True).create({
                'name': 'Swiss Partner',
                'phone': '+41313808316',
            })

    def test_local_caller_matches_e164_partner(self):
        """Local-format caller ID matches a partner stored in E.164."""
        found = self.env['res.partner'].get_partner_by_number('0313808316')
        self.assertEqual(found, self.swiss_partner)

    def test_e164_caller_matches_e164_partner(self):
        """E.164 caller ID still matches via the first search (regression)."""
        found = self.env['res.partner'].get_partner_by_number('+41313808316')
        self.assertEqual(found, self.swiss_partner)

    def test_unknown_number_returns_empty(self):
        """Unknown number normalizes but still matches nobody."""
        found = self.env['res.partner'].get_partner_by_number('+490000000000')
        self.assertFalse(found)


@tagged('at_install', '-post_install')
class TestGetPartnerByNumberSanitized(ConnectTestCommon):
    """Issue #9: an inbound caller ID in full international (E.164) format must
    resolve to a partner whose number is stored in local format.

    The softphone/provider delivers the caller as '+41795000992' (matching the
    stored phone_sanitized), while the partner is saved as the local
    '079 500 09 92'. phone_mobile_search compares the raw local value and the
    E.164 lookup never matches it (ADR-024 only covered the reverse storage),
    so get_partner_by_number falls back to a phone_sanitized match (ADR-029).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # phone_sanitized is computed against the main company's country, and
        # get_partner_by_number normalizes against res.company.browse(1); pin
        # it to CH so '079 500 09 92' sanitizes to '+41795000992'.
        cls.env['res.company'].browse(1).country_id = cls.env.ref('base.ch')
        cls.local_partner = cls.env['res.partner'].with_context(
            no_clear_cache=True).create({
                'name': 'Local Swiss Partner',
                'phone': '079 500 09 92',
            })

    def test_e164_caller_matches_local_partner(self):
        """E.164 caller ID resolves a partner stored in local format."""
        found = self.env['res.partner'].get_partner_by_number('+41795000992')
        self.assertEqual(found, self.local_partner)

    def test_local_caller_still_matches_local_partner(self):
        """Local-format caller ID still matches (regression)."""
        found = self.env['res.partner'].get_partner_by_number('0795000992')
        self.assertEqual(found, self.local_partner)

    def test_unknown_e164_returns_empty(self):
        """An E.164 caller with no matching partner returns empty."""
        found = self.env['res.partner'].get_partner_by_number('+41799999999')
        self.assertFalse(found)
