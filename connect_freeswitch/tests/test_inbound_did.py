# -*- coding: utf-8 -*-
"""Tests for inbound DID routing in connect_freeswitch.

Covers issue #42: the rendered dialplan regex must match the FreeSWITCH-side
``destination_number`` regardless of whether the trunk delivers the DID with or
without a leading ``+``, and the record lookup must tolerate the same mismatch.
"""
import re

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


def _expression(dialplan_xml):
    """Extract the regex from ``expression="..."`` in a rendered dialplan."""
    m = re.search(r'expression="([^"]+)"', dialplan_xml)
    assert m, "no condition expression rendered:\n%s" % dialplan_xml
    return m.group(1)


@tagged("post_install", "-at_install", "connect_freeswitch", "inbound_did")
class TestInboundDidRouting(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Number = cls.env["connect.freeswitch.number"]

    # ------------------------------------------------------------------
    # Rendered regex matches both +/no-+ forms of the destination_number
    # ------------------------------------------------------------------

    def test_regex_stored_with_plus_matches_both_forms(self):
        num = self.Number.create({"phone_number": "+41215121140"})
        expr = _expression(num.generate_dialplan({}))
        # Trunk may send either form; both must match the rendered regex.
        self.assertTrue(re.match(expr, "41215121140"))
        self.assertTrue(re.match(expr, "+41215121140"))
        # A different number must NOT match.
        self.assertIsNone(re.match(expr, "41215121141"))

    def test_regex_stored_without_plus_matches_both_forms(self):
        num = self.Number.create({"phone_number": "41215121140"})
        expr = _expression(num.generate_dialplan({}))
        self.assertTrue(re.match(expr, "41215121140"))
        self.assertTrue(re.match(expr, "+41215121140"))
        self.assertIsNone(re.match(expr, "4121512114"))

    def test_render_sets_number_id_and_no_strict_undefined(self):
        # A bare number (no destination) renders the 404 branch but must still
        # render every template variable (StrictUndefined would raise otherwise).
        num = self.Number.create({"phone_number": "+15550001111"})
        xml = num.generate_dialplan({})
        self.assertIn("odoo_call_direction=inbound", xml)
        self.assertIn("odoo_number_id=%s" % num.id, xml)
        self.assertIn('name="did_15550001111"', xml)

    # ------------------------------------------------------------------
    # _find_by_did tolerates the +/no-+ mismatch in both directions
    # ------------------------------------------------------------------

    def test_find_by_did_stored_with_plus_found_without(self):
        num = self.Number.create({"phone_number": "+41215121140"})
        self.assertEqual(self.Number._find_by_did("41215121140").id, num.id)

    def test_find_by_did_stored_without_plus_found_with(self):
        num = self.Number.create({"phone_number": "41215121140"})
        self.assertEqual(self.Number._find_by_did("+41215121140").id, num.id)

    def test_find_by_did_exact_match_takes_precedence(self):
        num = self.Number.create({"phone_number": "+41215121140"})
        self.assertEqual(self.Number._find_by_did("+41215121140").id, num.id)

    def test_find_by_did_unmatched_returns_empty(self):
        self.assertFalse(self.Number._find_by_did("99999999999"))

    def test_find_by_did_empty_returns_empty(self):
        self.assertFalse(self.Number._find_by_did(""))


@tagged("post_install", "-at_install", "connect_freeswitch", "inbound_did")
class TestInboundDidCallerName(TransactionCase):
    """Issue #9: the inbound DID dialplan sets effective_caller_id_name to the
    matched partner's name, so the WebRTC softphone shows the contact instead
    of a bare number. The caller number arrives in the mod_xml_curl dialplan
    request params (Caller-Caller-ID-Number)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # phone_sanitized / get_partner_by_number normalize against the main
        # company country; pin CH so '079 500 09 92' == '+41795000992'.
        cls.env["res.company"].browse(1).country_id = cls.env.ref("base.ch")
        cls.partner = cls.env["res.partner"].with_context(
            no_clear_cache=True).create({
                "name": "Ada Lovelace",
                "phone": "079 500 09 92",
            })
        cls.number = cls.env["connect.freeswitch.number"].create(
            {"phone_number": "+41215121140"})

    def test_matched_partner_name_injected(self):
        xml = self.number.generate_dialplan(
            {"Caller-Caller-ID-Number": "+41795000992"})
        self.assertIn(
            'data="effective_caller_id_name=Ada Lovelace"', xml)

    def test_unknown_caller_no_injection(self):
        xml = self.number.generate_dialplan(
            {"Caller-Caller-ID-Number": "+41799999999"})
        self.assertNotIn("effective_caller_id_name=", xml)

    def test_no_caller_param_no_injection(self):
        # Existing callers pass {}; StrictUndefined must not raise and no
        # caller name is injected.
        xml = self.number.generate_dialplan({})
        self.assertNotIn("effective_caller_id_name=", xml)
