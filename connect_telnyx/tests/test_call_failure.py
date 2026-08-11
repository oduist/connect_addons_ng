# -*- coding: utf-8 -*-
from types import SimpleNamespace
from unittest.mock import patch

from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.connect_telnyx.models.settings import Settings


def _client_with_credit(available):
    """Build a fake Telnyx client whose balance endpoint reports
    the given available credit."""
    balance = SimpleNamespace(
        retrieve=lambda: SimpleNamespace(
            data=SimpleNamespace(
                available_credit=available,
                balance=available,
                currency='USD',
            )
        )
    )
    return SimpleNamespace(balance=balance)


@tagged('at_install', '-post_install')
class TestTelnyxCallFailure(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Settings = cls.env['connect.settings']
        cls.plain_user = new_test_user(
            cls.env, login='tcf_plain',
            groups='base.group_user,connect.group_user')
        cls.admin_user = new_test_user(
            cls.env, login='tcf_admin',
            groups='base.group_user,connect.group_admin')

    def test_balance_blocked_admin_sees_amount(self):
        with patch.object(Settings, 'get_telnyx_client',
                          return_value=_client_with_credit('-0.01')):
            res = self.Settings.with_user(
                self.admin_user).telnyx_check_call_failure(
                    cause='UNALLOCATED_NUMBER', sip_code=404)
        self.assertTrue(res['balance_blocked'])
        self.assertIn('-0.01', res['message'])

    def test_balance_blocked_plain_user_no_amount(self):
        with patch.object(Settings, 'get_telnyx_client',
                          return_value=_client_with_credit('-0.01')):
            res = self.Settings.with_user(
                self.plain_user).telnyx_check_call_failure()
        self.assertTrue(res['balance_blocked'])
        self.assertTrue(res['message'])
        self.assertNotIn('-0.01', res['message'])

    def test_positive_balance_not_blocked(self):
        with patch.object(Settings, 'get_telnyx_client',
                          return_value=_client_with_credit('25.00')):
            res = self.Settings.with_user(
                self.plain_user).telnyx_check_call_failure()
        self.assertFalse(res['balance_blocked'])

    def test_api_error_swallowed(self):
        with patch.object(Settings, 'get_telnyx_client',
                          side_effect=Exception('boom')):
            res = self.Settings.with_user(
                self.plain_user).telnyx_check_call_failure()
        self.assertFalse(res['balance_blocked'])

    def test_user_without_connect_groups_gets_nothing(self):
        user = new_test_user(self.env, login='tcf_nogroup')
        with patch.object(Settings, 'get_telnyx_client',
                          return_value=_client_with_credit('-0.01')):
            res = self.Settings.with_user(user).telnyx_check_call_failure()
        self.assertFalse(res['balance_blocked'])
