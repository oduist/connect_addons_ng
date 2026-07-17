# -*- coding: utf-8 -*-
"""Tests for sofia 'external' profile reload on gateway changes.

Covers issue #38: creating the very first gateway must *start* the external
sofia profile (a plain 'restart' is a no-op when the profile was never loaded),
and the reload must be deferred to post-commit so FreeSWITCH's separate
xml_curl request reads the committed gateway row.
"""
from unittest import mock

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "connect_freeswitch", "gateway")
class TestGatewaySofiaReload(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Gateway = cls.env["connect.freeswitch.gateway"]
        cls.Settings = cls.env["connect.settings"]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _patch_api(self, status_return):
        """Replace connect.settings.freeswitch_api with a recorder that
        returns ``status_return`` for the 'status profile external' query and
        'OK' for everything else. Returns (calls, patcher)."""
        calls = []

        def fake_api(command, args=""):
            calls.append((command, args))
            if command == "sofia" and args == "status profile external":
                return status_return
            return "OK"

        patcher = mock.patch.object(
            type(self.Settings), "freeswitch_api", side_effect=fake_api
        )
        return calls, patcher

    # ------------------------------------------------------------------
    # _apply_sofia_profile_reload: start when absent, restart when running
    # ------------------------------------------------------------------

    def test_apply_reload_starts_when_profile_absent(self):
        calls, patcher = self._patch_api("Invalid Profile!\n")
        with patcher:
            self.Gateway._apply_sofia_profile_reload()
        self.assertIn(("sofia", "status profile external"), calls)
        self.assertIn(("sofia", "profile external start"), calls)
        self.assertNotIn(
            ("sofia", "profile external restart reloadxml"), calls
        )

    def test_apply_reload_starts_when_api_unreachable(self):
        # freeswitch_api returns False when XML-RPC is unreachable.
        calls, patcher = self._patch_api(False)
        with patcher:
            self.Gateway._apply_sofia_profile_reload()
        self.assertIn(("sofia", "profile external start"), calls)
        self.assertNotIn(
            ("sofia", "profile external restart reloadxml"), calls
        )

    def test_apply_reload_restarts_when_running(self):
        running = (
            "Name                external\n"
            "Domain Name         N/A\n"
            "Auto-NAT            false\n"
            "State               RUNNING (0)\n"
        )
        calls, patcher = self._patch_api(running)
        with patcher:
            self.Gateway._apply_sofia_profile_reload()
        self.assertIn(
            ("sofia", "profile external restart reloadxml"), calls
        )
        self.assertNotIn(("sofia", "profile external start"), calls)

    def test_apply_acl_reload_calls_reloadacl(self):
        calls, patcher = self._patch_api("OK")
        with patcher:
            self.Gateway._apply_acl_reload()
        self.assertIn(("reloadacl", ""), calls)

    # ------------------------------------------------------------------
    # create/write/unlink defer the reload to post-commit, not inline
    #
    # The reload must NOT touch FreeSWITCH synchronously inside the open
    # transaction (the new/changed gateway is not committed yet, so the
    # separate xml_curl request can't see it). We assert nothing fires during
    # the ORM call, then flush the post-commit queue with the public
    # ``cr.postcommit.run()`` (what a real COMMIT does) and assert the reload
    # fired then.
    # ------------------------------------------------------------------

    def test_create_defers_reload_to_postcommit(self):
        calls, patcher = self._patch_api("Invalid Profile!")
        with patcher:
            self.Gateway.create({"name": "gw1", "proxy": "sip.example.com"})
            # Deferred: nothing sent to FreeSWITCH during create().
            self.assertEqual(calls, [])
            self.env.cr.postcommit.run()
            # On commit the profile is probed and started (it was absent).
            self.assertIn(("sofia", "status profile external"), calls)
            self.assertIn(("sofia", "profile external start"), calls)
            # No inbound IPs -> no ACL reload.
            self.assertNotIn(("reloadacl", ""), calls)

    def test_write_defers_reload_to_postcommit(self):
        calls, patcher = self._patch_api("Invalid Profile!")
        with patcher:
            gw = self.Gateway.create(
                {"name": "gw2", "proxy": "sip.example.com"})
            self.env.cr.postcommit.run()  # flush the create reload
            calls.clear()
            gw.write({"proxy": "sip2.example.com"})
            self.assertEqual(calls, [])  # write deferred too
            self.env.cr.postcommit.run()
            self.assertIn(("sofia", "status profile external"), calls)

    def test_unlink_defers_reload_to_postcommit(self):
        calls, patcher = self._patch_api("Invalid Profile!")
        with patcher:
            gw = self.Gateway.create(
                {"name": "gw3", "proxy": "sip.example.com"})
            self.env.cr.postcommit.run()
            calls.clear()
            gw.unlink()
            self.assertEqual(calls, [])
            self.env.cr.postcommit.run()
            self.assertIn(("sofia", "status profile external"), calls)

    def test_inbound_ips_also_reloads_acl_on_commit(self):
        # A gateway with inbound IPs reloads both the sofia profile and the ACL
        # after commit.
        calls, patcher = self._patch_api("Invalid Profile!")
        with patcher:
            self.Gateway.create(
                {
                    "name": "gw4",
                    "proxy": "sip.example.com",
                    "inbound_ips": "185.3.68.0/24",
                }
            )
            self.assertEqual(calls, [])
            self.env.cr.postcommit.run()
        self.assertIn(("sofia", "profile external start"), calls)
        self.assertIn(("reloadacl", ""), calls)
