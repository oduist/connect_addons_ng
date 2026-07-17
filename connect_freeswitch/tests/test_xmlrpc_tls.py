# -*- coding: utf-8 -*-
"""Tests for HTTPS XML-RPC connectivity to FreeSWITCH.

Covers the managed XML-RPC edge: ``_freeswitch_rpc()`` always reaches
mod_xml_rpc over verified HTTPS on port 443, uses the fixed internal username,
and rotates its hidden password when the public host changes (ADR-044).
"""
import ssl
from unittest import mock

from odoo.exceptions import ValidationError
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
        S.sudo().set_param("freeswitch_xmlrpc_password", "fspass")

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
        result, error, url, context = self._call_rpc()
        self.assertIsNone(error)
        self.assertEqual(result, "OK")
        # Always HTTPS, never plain http:// — the whole point of issue #37.
        self.assertTrue(
            url.startswith("https://"),
            "XML-RPC URL must use https, got: %s" % url,
        )
        # Credentials + default public Traefik port (443) + RPC2 path.
        self.assertIn("odoo:fspass@fs.example.com:443/RPC2", url)

    def test_uses_verifying_context(self):
        _result, _error, _url, context = self._call_rpc()
        self.assertIsInstance(context, ssl.SSLContext)
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)

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

    def test_connection_details_are_not_configurable(self):
        fields_map = self.env["connect.settings"]._fields
        self.assertNotIn("freeswitch_xmlrpc_port", fields_map)
        self.assertNotIn("freeswitch_xmlrpc_user", fields_map)
        self.assertNotIn("display_freeswitch_xmlrpc_password", fields_map)
        self.assertNotIn("freeswitch_xmlrpc_tls_verify", fields_map)

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

    def test_host_change_rotates_hidden_password(self):
        Settings = self.env["connect.settings"].sudo()
        rec = Settings.search([], limit=1) or Settings.create({})
        rec.write({"freeswitch_xmlrpc_host": "old.example.com"})
        rec.write({"freeswitch_xmlrpc_password": "old-password"})
        with mock.patch(
                "odoo.addons.connect_freeswitch.models.settings."
                "secrets.token_urlsafe",
                return_value="rotated-password",
        ) as generate:
            rec.write({"freeswitch_xmlrpc_host": " New.Example.COM. "})
            self.assertEqual(rec.freeswitch_xmlrpc_host, "new.example.com")
            self.assertEqual(
                Settings.get_param("freeswitch_xmlrpc_password"),
                "rotated-password",
            )
            generate.assert_called_once_with(32)

            # A spelling-only update normalizes to the same host and does not
            # rotate the credential again.
            rec.write({"freeswitch_xmlrpc_host": "NEW.EXAMPLE.COM"})
            generate.assert_called_once_with(32)

    def test_host_rejects_url_or_port(self):
        Settings = self.env["connect.settings"].sudo()
        rec = Settings.search([], limit=1) or Settings.create({})
        for invalid_host in (
                "https://fs.example.com", "fs.example.com:443", "fs/path"):
            with self.assertRaises(ValidationError):
                rec.write({"freeswitch_xmlrpc_host": invalid_host})
