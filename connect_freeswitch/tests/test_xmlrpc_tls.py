# -*- coding: utf-8 -*-
"""Tests for HTTPS XML-RPC connectivity to FreeSWITCH.

Covers issue #37: ``_freeswitch_rpc()`` must always reach mod_xml_rpc over
HTTPS (Traefik terminates TLS in front of it) so the HTTP Basic Auth
credential never travels in cleartext, and the ``freeswitch_xmlrpc_tls_verify``
setting must toggle certificate verification (ADR-030).
"""
import ssl
from unittest import mock

from odoo.tests import tagged, new_test_user
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "connect_freeswitch", "xmlrpc")
class TestXmlRpcTls(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Settings = cls.env["connect.settings"]
        S = cls.Settings
        S.set_param("freeswitch_xmlrpc_host", "fs.example.com")
        S.set_param("freeswitch_xmlrpc_user", "fsuser")
        S.set_param("freeswitch_xmlrpc_password", "fspass")

    def _call_rpc(self):
        """Run _freeswitch_rpc('status') with ServerProxy mocked.

        Returns the (result, error) tuple plus the url and ssl context the
        proxy was constructed with.
        """
        with mock.patch("xmlrpc.client.ServerProxy") as proxy:
            proxy.return_value.freeswitch.api.return_value = "OK"
            result, error = self.Settings._freeswitch_rpc("status")
        url = proxy.call_args.args[0]
        context = proxy.call_args.kwargs.get("context")
        return result, error, url, context

    def test_url_is_https_with_credentials_and_rpc2_path(self):
        self.Settings.set_param("freeswitch_xmlrpc_tls_verify", True)
        result, error, url, context = self._call_rpc()
        self.assertIsNone(error)
        self.assertEqual(result, "OK")
        # Always HTTPS, never plain http:// — the whole point of issue #37.
        self.assertTrue(
            url.startswith("https://"),
            "XML-RPC URL must use https, got: %s" % url,
        )
        # Credentials + default public Traefik port (443) + RPC2 path.
        self.assertIn("fsuser:fspass@fs.example.com:443/RPC2", url)

    def test_verify_on_uses_verifying_context(self):
        self.Settings.set_param("freeswitch_xmlrpc_tls_verify", True)
        _result, _error, _url, context = self._call_rpc()
        self.assertIsInstance(context, ssl.SSLContext)
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)

    def test_verify_off_disables_verification(self):
        self.Settings.set_param("freeswitch_xmlrpc_tls_verify", False)
        _result, _error, _url, context = self._call_rpc()
        self.assertIsInstance(context, ssl.SSLContext)
        self.assertFalse(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_NONE)

    def test_custom_public_port_is_honoured(self):
        # Operators running Traefik on a non-standard HTTPS port.
        self.Settings.set_param("freeswitch_xmlrpc_port", 8443)
        self.Settings.set_param("freeswitch_xmlrpc_tls_verify", True)
        _result, _error, url, _context = self._call_rpc()
        self.assertIn("@fs.example.com:8443/RPC2", url)

    def test_not_configured_without_host(self):
        self.Settings.set_param("freeswitch_xmlrpc_host", "")
        result, error = self.Settings._freeswitch_rpc("status")
        self.assertIsNone(result)
        self.assertEqual(error, "NOT CONFIGURED")


@tagged("post_install", "-at_install", "connect_freeswitch", "xmlrpc")
class TestXmlRpcPasswordAccess(TransactionCase):
    """The mod_xml_rpc password is a control-plane credential and must never be
    readable by a non-administrator, including over RPC through get_param."""

    def test_stored_password_field_is_admin_only(self):
        field = self.env["connect.settings"]._fields["freeswitch_xmlrpc_password"]
        self.assertEqual(field.groups, "connect.group_admin")

    def test_non_admin_get_param_returns_no_password(self):
        Settings = self.env["connect.settings"]
        Settings.set_param("freeswitch_xmlrpc_password", "s3cr3t")
        # Sudo / admin path still sees the real value (controllers rely on this).
        self.assertEqual(
            Settings.sudo().get_param("freeswitch_xmlrpc_password"), "s3cr3t")
        # A plain internal user (connect.group_user, not admin) does not.
        user = new_test_user(
            self.env,
            login="plain_xmlrpc_user",
            groups="base.group_user,connect.group_user",
        )
        self.assertFalse(
            Settings.with_user(user).get_param("freeswitch_xmlrpc_password"))

    def test_display_field_masks_and_stores(self):
        Settings = self.env["connect.settings"].sudo()
        rec = Settings.search([], limit=1) or Settings.create({})
        rec.write({"display_freeswitch_xmlrpc_password": "topsecret"})
        # The real password is copied to the admin-only stored field…
        self.assertEqual(
            Settings.get_param("freeswitch_xmlrpc_password"), "topsecret")
        # …and the displayed value is masked back to asterisks.
        self.assertEqual(
            rec.display_freeswitch_xmlrpc_password, "*" * len("topsecret"))
