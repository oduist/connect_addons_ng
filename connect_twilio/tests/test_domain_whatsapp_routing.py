# -*- coding: utf-8 -*-
"""Inbound WhatsApp calls fall back to the number's own destination.

``route_call()`` used to consult only ``connect.twilio.exten``, so a
WhatsApp call died on "Whatsapp Extension not found" even when
``connect.twilio.number`` already routed that very number to a user —
the same number a plain PSTN call reached without any extension.
"""
from unittest.mock import patch

from odoo.tests import tagged

from .common import TwilioTestCommon

BY_NUMBER = '<Response><Say>routed by number</Say></Response>'
BY_EXTEN = '<Response><Say>routed by exten</Say></Response>'


@tagged('at_install', '-post_install')
class TestDomainWhatsappRouting(TwilioTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.connect_user = cls._create_connect_user('tw_wa_routing')
        taken = set(cls.env['connect.twilio.number'].search(
            []).mapped('phone_number'))
        taken |= set(cls.env['connect.twilio.exten'].search(
            []).mapped('number'))
        free = (
            '+1999555{:04d}'.format(n) for n in range(1000, 1100)
        )
        cls.wa_number = next(n for n in free if n not in taken)
        cls.unknown_number = next(
            n for n in free if n not in taken and n != cls.wa_number)
        cls.number = cls.env['connect.twilio.number'].create({
            'phone_number': cls.wa_number,
            'destination': 'user',
            'user': cls.connect_user.id,
        })
        cls.Domain = cls.env['connect.twilio.domain']

    def _route(self, to_val):
        """Route a call, stubbing out everything but the routing decision."""
        request = {
            'CallSid': 'CAwaroute',
            'Caller': 'whatsapp:+37360681783',
            'Called': to_val,
            'To': to_val,
            'Direction': 'inbound',
            'CallStatus': 'in-progress',
        }
        License = type(self.env['oduist.license'])
        Call = type(self.env['connect.call'])
        Number = type(self.env['connect.twilio.number'])
        Exten = type(self.env['connect.twilio.exten'])
        with patch.object(License, 'check_license', return_value=True), \
                patch.object(Call, 'on_call_status', return_value=None), \
                patch.object(Number, 'render', return_value=BY_NUMBER), \
                patch.object(Exten, 'render', return_value=BY_EXTEN):
            return self.Domain.route_call(request)

    def test_whatsapp_falls_back_to_the_number_destination(self):
        self.assertEqual(
            self._route('whatsapp:' + self.wa_number), BY_NUMBER)

    def test_extension_still_wins_over_the_number(self):
        self.env['connect.twilio.exten'].create({'number': self.wa_number})
        self.assertEqual(
            self._route('whatsapp:' + self.wa_number), BY_EXTEN)

    def test_unknown_whatsapp_number_keeps_the_error(self):
        result = self._route('whatsapp:' + self.unknown_number)
        self.assertIn('Extension not found', result)
