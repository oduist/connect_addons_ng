# -*- coding: utf-8 -*-
"""connect.twilio.outgoing_callerid tests (moved from the shared core
suite after the provider model separation, ADR-031)."""
from odoo.tests import tagged
from odoo.exceptions import ValidationError

from .common import TwilioTestCommon


@tagged('at_install', '-post_install')
class TestTwilioOutgoingCallerid(TwilioTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Cid = cls.env['connect.twilio.outgoing_callerid'].with_context(
            skip_validation=True)

    def test_create_callerid(self):
        cid = self.Cid.create({
            'friendly_name': 'Main', 'number': '+15550001111',
        })
        self.assertTrue(cid.id)
        self.assertIn('+15550001111', cid.name)

    def test_number_e164_constraint(self):
        with self.assertRaises(ValidationError):
            self.Cid.create({
                'friendly_name': 'Bad', 'number': '0795001122',
            })

    def test_number_unique(self):
        self.Cid.create({'friendly_name': 'A', 'number': '+15550002222'})
        with self.assertRaises(Exception):
            self.Cid.create({'friendly_name': 'B', 'number': '+15550002222'})

    def test_is_default_reset(self):
        """Setting a new default clears the flag on other records."""
        a = self.Cid.create({
            'friendly_name': 'A', 'number': '+15550003333',
            'callerid_type': 'number', 'is_default': True,
        })
        b = self.Cid.create({
            'friendly_name': 'B', 'number': '+15550004444',
            'callerid_type': 'number',
        })
        b.is_default = True
        self.assertFalse(a.is_default)
        self.assertTrue(b.is_default)

    def test_user_link(self):
        cid = self.Cid.create({
            'friendly_name': 'U', 'number': '+15550005555',
        })
        user = self._create_connect_user('tw_ciduser1',
                                         twilio_outgoing_callerid=cid.id)
        self.assertEqual(cid.callerid_users, user)
