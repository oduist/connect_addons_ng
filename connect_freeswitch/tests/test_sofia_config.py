# -*- coding: utf-8 -*-
"""Tests for the sofia.conf xml_curl response (ADR-047).

The `external` profile is served from Odoo on demand. A fresh env has no
gateway records, and gating the whole response on gateways left FreeSWITCH
without any sofia config at all ("0 profiles", `Failure starting external`, no
SIP registration possible — ODU-45). The profile must be served
unconditionally, with gateways injected only when they exist.
"""
import base64
from unittest import mock

from odoo.tests import tagged
from odoo.tests.common import HttpCase


@tagged("post_install", "-at_install", "connect_freeswitch", "sofia_config")
class TestSofiaConfig(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Gateway = cls.env["connect.freeswitch.gateway"]
        # Gateway writes schedule a post-commit reload (ADR-028); keep every
        # FreeSWITCH call in this test class in-process.
        patcher = mock.patch.object(
            type(cls.env["connect.settings"]), "freeswitch_api",
            return_value="OK",
        )
        patcher.start()
        cls.addClassCleanup(patcher.stop)
        # A fresh env has no gateways; leftovers from other tests or demo data
        # would mask the regression.
        cls.Gateway.search([]).write({"active": False})

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _fetch_sofia_conf(self):
        """POST the xml_curl configuration lookup FreeSWITCH sends for sofia."""
        token = self.env["connect.settings"].sudo().get_param(
            "freeswitch_webhook_token")
        cred = base64.b64encode(("freeswitch:%s" % token).encode()).decode()
        resp = self.url_open(
            "/freeswitch/xml",
            data={"section": "configuration", "key_value": "sofia.conf"},
            headers={"Authorization": "Basic %s" % cred},
        )
        self.assertEqual(resp.status_code, 200)
        return resp.text

    def _create_gateway(self, **vals):
        gw = self.Gateway.create(dict(
            {"name": "gw-sofia", "proxy": "sip.example.com"}, **vals))
        self.env.flush_all()
        return gw

    # ------------------------------------------------------------------
    # The regression: no gateways must still yield a usable sofia.conf
    # ------------------------------------------------------------------

    def test_external_profile_served_with_no_gateways(self):
        self.assertFalse(self.Gateway.search([("active", "=", True)]))
        body = self._fetch_sofia_conf()
        self.assertNotIn("not found", body)
        self.assertIn('<configuration name="sofia.conf"', body)
        self.assertIn('<profile name="external"', body)
        # The SIP registration surface must be there on a bare env.
        self.assertIn('<param name="sip-port" value="5080"/>', body)

    def test_no_gateway_element_when_none_exist(self):
        body = self._fetch_sofia_conf()
        self.assertIn("<gateways>", body)
        self.assertNotIn("<gateway ", body)

    # ------------------------------------------------------------------
    # ...and a gateway is still injected into that same profile
    # ------------------------------------------------------------------

    def test_gateway_injected_when_present(self):
        self._create_gateway(name="gw-injected", proxy="sip.trunk.example")
        body = self._fetch_sofia_conf()
        self.assertIn('<profile name="external"', body)
        self.assertIn('<gateway name="gw-injected">', body)
        self.assertIn('value="sip.trunk.example"', body)

    def test_inactive_gateway_not_injected(self):
        gw = self._create_gateway(name="gw-archived", proxy="sip.old.example")
        gw.active = False
        self.env.flush_all()
        body = self._fetch_sofia_conf()
        # Profile still served, gateway gone.
        self.assertIn('<profile name="external"', body)
        self.assertNotIn("gw-archived", body)
