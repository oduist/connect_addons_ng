# -*- coding: utf-8 -*-
"""connect.infobip.outgoing_callerid tests (E.164 + single-default logic,
deliberately duplicated per ADR-031/ADR-036)."""
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import InfobipTestCommon


@tagged('at_install', '-post_install')
class TestInfobipOutgoingCallerid(InfobipTestCommon):

    def test_create_valid(self):
        rec = self.env['connect.infobip.outgoing_callerid'].create({
            'number': '+15550001111',
            'friendly_name': 'Main',
        })
        self.assertTrue(rec.id)
        self.assertIn('+15550001111', rec.name)

    def test_e164_constraint(self):
        with self.assertRaises(ValidationError):
            self.env['connect.infobip.outgoing_callerid'].create({
                'number': '15550001111',
                'friendly_name': 'No Plus',
            })
        with self.assertRaises(ValidationError):
            self.env['connect.infobip.outgoing_callerid'].create({
                'number': '+1555000BAD',
                'friendly_name': 'Letters',
            })

    def test_single_default(self):
        first = self.env['connect.infobip.outgoing_callerid'].create({
            'number': '+15550001111',
            'friendly_name': 'One',
            'is_default': True,
        })
        second = self.env['connect.infobip.outgoing_callerid'].create({
            'number': '+15550002222',
            'friendly_name': 'Two',
            'is_default': True,
        })
        self.assertTrue(second.is_default)
        self.assertFalse(first.is_default)

    def test_unique_number(self):
        self.env['connect.infobip.outgoing_callerid'].create({
            'number': '+15550003333',
            'friendly_name': 'Uniq',
        })
        with self.assertRaises(Exception):
            self.env['connect.infobip.outgoing_callerid'].create({
                'number': '+15550003333',
                'friendly_name': 'Dup',
            })
