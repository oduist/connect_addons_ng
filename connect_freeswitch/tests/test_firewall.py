# -*- coding: utf-8 -*-
"""Tests for the firewall-related additions in connect_freeswitch:
models, validation, postcommit triggers, XML-RPC methods, retention cron.

These tests exercise everything that lives inside Odoo. The standalone
firewall service is covered separately by its own unit tests under
connect_freeswitch/deploy/firewall/tests/.
"""
import secrets
from datetime import timedelta
from unittest import mock

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "connect_freeswitch", "firewall")
class TestFirewallModels(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Whitelist = cls.env["connect.firewall.whitelist"]
        cls.Blacklist = cls.env["connect.firewall.blacklist"]
        cls.Event = cls.env["connect.firewall.event"]
        cls.Agent = cls.env["connect.firewall.agent"]
        cls.Settings = cls.env["connect.settings"].sudo()

    # ------------------------------------------------------------------
    # IP / CIDR validation on whitelist / blacklist
    # ------------------------------------------------------------------

    def test_whitelist_accepts_ipv4(self):
        rec = self.Whitelist.create({"name": "office", "ip_or_cidr": "1.2.3.4"})
        self.assertTrue(rec.id)

    def test_whitelist_accepts_cidr(self):
        rec = self.Whitelist.create({"name": "lan", "ip_or_cidr": "10.0.0.0/8"})
        self.assertTrue(rec.id)

    def test_whitelist_rejects_garbage(self):
        with self.assertRaises(ValidationError):
            self.Whitelist.create({"name": "bad", "ip_or_cidr": "not-an-ip"})

    def test_whitelist_unique(self):
        self.Whitelist.create({"name": "first", "ip_or_cidr": "5.5.5.5"})
        with self.assertRaises(ValidationError):
            self.Whitelist.create({"name": "dup", "ip_or_cidr": "5.5.5.5"})

    def test_blacklist_validation_same_as_whitelist(self):
        with self.assertRaises(ValidationError):
            self.Blacklist.create({"name": "x", "ip_or_cidr": "999.0.0.1"})


@tagged("post_install", "-at_install", "connect_freeswitch", "firewall")
class TestFirewallSettingsValidation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Settings = cls.env["connect.settings"].sudo()

    def test_token_too_short_rejected(self):
        with self.assertRaises(ValidationError):
            self.Settings.set_param("display_firewall_service_token", "1234")

    def test_token_with_forbidden_char_rejected(self):
        # 30 chars but contains '$'
        bad = "a" * 29 + "$"
        with self.assertRaises(ValidationError):
            self.Settings.set_param("display_firewall_service_token", bad)

    def test_token_strong_accepted(self):
        good = secrets.token_urlsafe(32)
        self.Settings.set_param("display_firewall_service_token", good)
        # After write, the displayed field has been masked; the real one
        # holds our value.
        self.assertEqual(self.Settings.get_param("firewall_service_token"), good)

    def test_password_too_short_rejected(self):
        with self.assertRaises(ValidationError):
            self.Settings.set_param("display_freeswitch_agent_password", "short")

    def test_password_with_space_rejected(self):
        with self.assertRaises(ValidationError):
            self.Settings.set_param(
                "display_freeswitch_agent_password", "has space inside"
            )

    def test_password_strong_accepted(self):
        good = secrets.token_urlsafe(20)
        self.Settings.set_param("display_freeswitch_agent_password", good)
        self.assertEqual(
            self.Settings.get_param("freeswitch_agent_password"), good
        )


@tagged("post_install", "-at_install", "connect_freeswitch", "firewall")
class TestFirewallAgentAPI(TransactionCase):
    """XML-RPC entry points the service calls."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Agent = cls.env["connect.firewall.agent"]
        cls.Whitelist = cls.env["connect.firewall.whitelist"]
        cls.Blacklist = cls.env["connect.firewall.blacklist"]
        cls.Event = cls.env["connect.firewall.event"]
        cls.Settings = cls.env["connect.settings"].sudo()

    def test_fetch_config_returns_required_keys(self):
        cfg = self.Agent.fetch_config()
        for k in (
            "firewall_enabled",
            "firewall_heartbeat_interval",
            "firewall_tcp_ports",
            "firewall_udp_ports",
            "firewall_banned_timeout",
            "firewall_authenticated_timeout",
            "firewall_expire_short_timeout",
            "firewall_expire_long_timeout",
            "firewall_service_token",
        ):
            self.assertIn(k, cfg, "fetch_config missing key %s" % k)

    def test_fetch_whitelist_returns_active_only(self):
        self.Whitelist.create({"name": "on", "ip_or_cidr": "11.0.0.0/24"})
        self.Whitelist.create(
            {"name": "off", "ip_or_cidr": "12.0.0.0/24", "active": False}
        )
        ips = [r["ip_or_cidr"] for r in self.Agent.fetch_whitelist()]
        self.assertIn("11.0.0.0/24", ips)
        self.assertNotIn("12.0.0.0/24", ips)

    def test_fetch_whitelist_carries_note(self):
        self.Whitelist.create(
            {"name": "office", "ip_or_cidr": "13.0.0.0/24", "note": "HQ"}
        )
        rec = next(
            r for r in self.Agent.fetch_whitelist() if r["ip_or_cidr"] == "13.0.0.0/24"
        )
        self.assertEqual(rec["name"], "office")
        self.assertEqual(rec["note"], "HQ")

    def test_fetch_blacklist_returns_active_only(self):
        self.Blacklist.create({"name": "on", "ip_or_cidr": "20.0.0.0/24"})
        self.Blacklist.create(
            {"name": "off", "ip_or_cidr": "21.0.0.0/24", "active": False}
        )
        ips = [r["ip_or_cidr"] for r in self.Agent.fetch_blacklist()]
        self.assertIn("20.0.0.0/24", ips)
        self.assertNotIn("21.0.0.0/24", ips)

    def test_report_event_creates_record(self):
        before = self.Event.search_count([])
        eid = self.Agent.report_event(
            {
                "event_type": "auto_ban",
                "ip": "192.0.2.1",
                "user_agent": "ua",
                "account_id": "1001",
                "details": "test",
            }
        )
        self.assertTrue(eid)
        self.assertEqual(self.Event.search_count([]), before + 1)
        rec = self.Event.browse(eid)
        self.assertEqual(rec.event_type, "auto_ban")
        self.assertEqual(rec.ip, "192.0.2.1")

    def test_report_event_handles_wrapped_payload(self):
        """aio_odoorpc sometimes wraps the dict in an extra list."""
        before = self.Event.search_count([])
        # Call as if the client put the dict inside *args (no kw).
        eid = self.Agent.report_event(
            [{"event_type": "auth_fail", "ip": "192.0.2.2"}]
        )
        self.assertTrue(eid)
        self.assertEqual(self.Event.search_count([]), before + 1)

    def test_report_event_rejects_missing_type(self):
        eid = self.Agent.report_event({"ip": "192.0.2.3"})
        self.assertFalse(eid)

    def test_report_heartbeat_updates_singleton(self):
        self.Agent.report_heartbeat(
            {
                "version": "test-1",
                "esl_connected": True,
                "bans_count": 5,
                "authenticated_count": 2,
                "uptime_seconds": 42,
            }
        )
        rec = self.Agent._get_singleton()
        self.assertEqual(rec.version, "test-1")
        self.assertTrue(rec.esl_connected)
        self.assertEqual(rec.bans_count, 5)
        self.assertEqual(rec.authenticated_count, 2)
        self.assertEqual(rec.uptime_seconds, 42)
        self.assertTrue(rec.last_seen)

    def test_report_applied_logs_event_and_returns_true(self):
        before = self.Event.search_count([])
        ok = self.Agent.report_applied("192.0.2.4", "unban", "ok")
        self.assertTrue(ok)
        # report_applied does not insert a connect.firewall.event itself
        # (it only writes to the agent singleton + sends a bus message);
        # so the count is unchanged.
        self.assertEqual(self.Event.search_count([]), before)


@tagged("post_install", "-at_install", "connect_freeswitch", "firewall")
class TestFirewallPostcommitSync(TransactionCase):
    """Whitelist/blacklist/settings writes must schedule a /firewall/sync."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Whitelist = cls.env["connect.firewall.whitelist"]
        cls.Settings = cls.env["connect.settings"].sudo()
        # Enable firewall so _trigger_sync actually fires.
        cls.Settings.set_param("firewall_enabled", True)
        cls.Settings.set_param(
            "firewall_service_url", "http://localhost:0/firewall"
        )
        cls.Settings.set_param("firewall_service_token", "x" * 32)

    def _capture_postcommit(self):
        """Return a list that grows with each postcommit callback the
        code under test schedules."""
        calls = []
        original_add = self.env.cr.postcommit.add

        def add(callback):
            calls.append(callback)
            return original_add(callback)

        return calls, add

    def test_whitelist_create_triggers_sync(self):
        calls, replacement = self._capture_postcommit()
        with mock.patch.object(self.env.cr.postcommit, "add", side_effect=replacement):
            self.Whitelist.create({"name": "office", "ip_or_cidr": "30.0.0.0/24"})
        self.assertTrue(calls, "create() did not schedule a postcommit callback")

    def test_whitelist_write_triggers_sync(self):
        rec = self.Whitelist.create({"name": "office", "ip_or_cidr": "31.0.0.0/24"})
        calls, replacement = self._capture_postcommit()
        with mock.patch.object(self.env.cr.postcommit, "add", side_effect=replacement):
            rec.write({"note": "updated"})
        self.assertTrue(calls)

    def test_whitelist_unlink_triggers_sync(self):
        rec = self.Whitelist.create({"name": "office", "ip_or_cidr": "32.0.0.0/24"})
        calls, replacement = self._capture_postcommit()
        with mock.patch.object(self.env.cr.postcommit, "add", side_effect=replacement):
            rec.unlink()
        self.assertTrue(calls)


@tagged("post_install", "-at_install", "connect_freeswitch", "firewall")
class TestFirewallEventRetention(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Event = cls.env["connect.firewall.event"]
        cls.Settings = cls.env["connect.settings"].sudo()

    def test_cron_cleanup_drops_old(self):
        self.Settings.set_param("firewall_event_retention_days", 7)
        old_ts = fields.Datetime.now() - timedelta(days=30)
        keep_ts = fields.Datetime.now() - timedelta(days=1)
        old = self.Event.create(
            {"event_type": "service_started", "ip": "1.1.1.1", "ts": old_ts}
        )
        keep = self.Event.create(
            {"event_type": "service_started", "ip": "2.2.2.2", "ts": keep_ts}
        )
        self.Event._cron_cleanup()
        self.assertFalse(old.exists())
        self.assertTrue(keep.exists())


@tagged("post_install", "-at_install", "connect_freeswitch", "firewall")
class TestFirewallEventUnbanAction(TransactionCase):
    """Unban button on auto_ban events: is_banned compute + action method."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Event = cls.env["connect.firewall.event"]
        cls.Agent = cls.env["connect.firewall.agent"]
        cls.Settings = cls.env["connect.settings"].sudo()
        cls.Settings.set_param("firewall_enabled", True)
        cls.Settings.set_param(
            "firewall_service_url", "http://service.invalid/firewall"
        )
        cls.Settings.set_param("firewall_service_token", "y" * 32)

    def test_is_banned_false_for_non_autoban(self):
        rec = self.Event.create({"event_type": "auth_success", "ip": "1.2.3.4"})
        with mock.patch.object(
            type(self.env["connect.firewall.agent"]),
            "_fetch_live_banned_ips",
            return_value={"1.2.3.4"},
        ):
            rec._compute_is_banned()
        self.assertFalse(rec.is_banned)

    def test_is_banned_true_when_ip_in_live_set(self):
        rec = self.Event.create({"event_type": "auto_ban", "ip": "1.2.3.5"})
        with mock.patch.object(
            type(self.env["connect.firewall.agent"]),
            "_fetch_live_banned_ips",
            return_value={"1.2.3.5"},
        ):
            rec._compute_is_banned()
        self.assertTrue(rec.is_banned)

    def test_action_unban_calls_service(self):
        rec = self.Event.create({"event_type": "auto_ban", "ip": "1.2.3.6"})
        with mock.patch.object(
            type(self.env["connect.firewall.agent"]),
            "_call_service_unban",
            return_value=(True, ""),
        ) as patched:
            action = rec.action_unban_ip()
        patched.assert_called_once()
        # action.tag should be 'display_notification' on success.
        self.assertEqual(action.get("tag"), "display_notification")
