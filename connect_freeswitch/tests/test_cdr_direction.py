# -*- coding: utf-8 -*-
"""Tests for CDR call-direction resolution in connect_freeswitch.

Covers issue #43: a call originated via ``fs_cli -x "originate ..."`` (or any
path that doesn't seed ``caller_pbx_user``) was labelled ``incoming`` even
though it left the system outbound. The dialplan stamps the business-logic
direction on the channel via ``odoo_call_direction``; the CDR handler must
honour it instead of FreeSWITCH's transport-level ``<channel_data><direction>``.
"""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.connect_freeswitch.controllers.freeswitch_cdr import (
    FreeSwitchCDRController,
)


def _cdr_xml(channel_direction, odoo_call_direction=None, with_variables=True):
    """Build a minimal mod_xml_cdr document for parser tests."""
    variables = ""
    if with_variables:
        extra = ""
        if odoo_call_direction is not None:
            extra = (
                "<odoo_call_direction>%s</odoo_call_direction>"
                % odoo_call_direction
            )
        variables = (
            "<variables>"
            "<uuid>11111111-1111-1111-1111-111111111111</uuid>"
            "%s"
            "</variables>" % extra
        )
    return (
        '<?xml version="1.0"?>'
        "<cdr>"
        "<channel_data><direction>%s</direction></channel_data>"
        "%s"
        "</cdr>" % (channel_direction, variables)
    )


@tagged("post_install", "-at_install", "connect_freeswitch", "cdr_direction")
class TestCdrParseDirection(TransactionCase):
    """`_parse_cdr_xml` must surface odoo_call_direction from <variables>."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ctrl = FreeSwitchCDRController()

    def test_parses_outgoing_variable(self):
        data = self.ctrl._parse_cdr_xml(
            _cdr_xml("inbound", odoo_call_direction="outgoing"))
        self.assertEqual(data["odoo_call_direction"], "outgoing")
        # Native FS direction is still parsed alongside it.
        self.assertEqual(data["direction"], "inbound")

    def test_parses_inbound_variable(self):
        data = self.ctrl._parse_cdr_xml(
            _cdr_xml("inbound", odoo_call_direction="inbound"))
        self.assertEqual(data["odoo_call_direction"], "inbound")

    def test_absent_variable_is_none(self):
        data = self.ctrl._parse_cdr_xml(
            _cdr_xml("inbound", odoo_call_direction=None))
        self.assertIsNone(data["odoo_call_direction"])

    def test_no_variables_block_is_none(self):
        data = self.ctrl._parse_cdr_xml(
            _cdr_xml("outbound", with_variables=False))
        self.assertIsNone(data["odoo_call_direction"])
        self.assertEqual(data["direction"], "outbound")


@tagged("post_install", "-at_install", "connect_freeswitch", "cdr_direction")
class TestCdrTechnicalDirection(TransactionCase):
    """`_cdr_technical_direction` prefers odoo_call_direction, else native."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Call = cls.env["connect.call"]

    def test_variable_outgoing_wins_over_native_inbound(self):
        # The exact #43 regression: originate leg is native 'inbound'.
        self.assertEqual(
            self.Call._cdr_technical_direction(
                {"odoo_call_direction": "outgoing", "direction": "inbound"}),
            "outbound-api",
        )

    def test_variable_inbound_maps_to_inbound(self):
        self.assertEqual(
            self.Call._cdr_technical_direction(
                {"odoo_call_direction": "inbound", "direction": "inbound"}),
            "inbound",
        )

    def test_variable_wins_over_conflicting_native(self):
        # Variable is authoritative even when native direction disagrees.
        self.assertEqual(
            self.Call._cdr_technical_direction(
                {"odoo_call_direction": "inbound", "direction": "outbound"}),
            "inbound",
        )

    def test_fallback_native_outbound(self):
        self.assertEqual(
            self.Call._cdr_technical_direction({"direction": "outbound"}),
            "outbound-api",
        )

    def test_fallback_native_inbound(self):
        self.assertEqual(
            self.Call._cdr_technical_direction({"direction": "inbound"}),
            "inbound",
        )

    def test_fallback_empty_defaults_inbound(self):
        self.assertEqual(self.Call._cdr_technical_direction({}), "inbound")
