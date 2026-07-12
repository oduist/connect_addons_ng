# -*- coding: utf-8 -*-
"""Ringback is set before every bridge so the caller hears ringing, not
silence (issue #113, ADR-029).

Renders each affected dialplan template with a minimal complete context
(the templates use Jinja StrictUndefined) and asserts both ``ringback``
and ``transfer_ringback`` are set to ``${us-ring}`` ahead of the bridge.
"""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'connect_freeswitch', 'ringback')
class TestRingback(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Template = cls.env['connect.freeswitch.template']

    def _assert_ringback(self, xml):
        # Both vars set, and before the bridge action.
        self.assertIn('data="ringback=${us-ring}"', xml)
        self.assertIn('data="transfer_ringback=${us-ring}"', xml)
        self.assertLess(
            xml.index('ringback=${us-ring}'),
            xml.index('application="bridge"'),
            "ringback must be set before the bridge action")

    def test_user_bridge_has_ringback(self):
        xml = self.Template.render('dialplan_user_bridge', {
            'number': '1001', 'user_id': 1, 'exten_id': False,
            'record_calls': False, 'recording_url': '',
            'fs_domain': 'fs.example.com',
        })
        self._assert_ringback(xml)

    def test_ring_group_has_ringback(self):
        xml = self.Template.render('dialplan_ring_group', {
            'callflow_id': 1, 'number': '2000', 'exten_id': False,
            'record_calls': False, 'recording_url': '',
            'bridge_string': 'user/1001@fs.example.com',
            'fifo_number': '', 'voicemail_enabled': False,
            'voicemail_user_number': '',
        })
        self._assert_ringback(xml)

    def test_ivr_choice_has_ringback(self):
        xml = self.Template.render('dialplan_ivr_choice', {
            'callflow_id': 1, 'digits': '1', 'digits_escaped': '1',
            'user_id': 1, 'user_number': '1001',
            'fs_domain': 'fs.example.com',
        })
        self._assert_ringback(xml)

    def test_ivr_bridge_has_ringback(self):
        xml = self.Template.render('dialplan_ivr', {
            'callflow_id': 1, 'number': '3000', 'lang': 'en',
            'prompt': 'Welcome', 'timeout': 5000, 'choices': [],
            'fs_domain': 'fs.example.com',
            'ring_bridge': 'user/1001@fs.example.com',
            'fifo_number': '', 'invalid_regex': '',
            'voicemail_enabled': False, 'voicemail_prompt': '',
            'voicemail_url': '',
            'dmachine_timeout': 100,
        })
        self._assert_ringback(xml)
