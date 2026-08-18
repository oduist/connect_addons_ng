# -*- coding: utf-8 -*-
"""Extension numbers must not be reported as E.164 phone numbers.

Twilio echoes a bare extension used as caller ID back as ``+100``; the
ledger has to store the extension itself.
"""
from odoo.tests import tagged

from .common import TwilioTestCommon


@tagged('at_install', '-post_install')
class TestChannelExtenNumber(TwilioTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Pick free numbers: the database under test already carries the
        # extensions the demo setup created.
        taken = set(cls.env['connect.twilio.exten'].search([]).mapped('number'))
        free = [str(n) for n in range(7000, 8000) if str(n) not in taken]
        cls.number, cls.unknown_number = free[0], free[1]
        cls.exten = cls.env['connect.twilio.exten'].create(
            {'number': cls.number})

    def _map(self, caller, called='client:demo@test.sip.twilio.com'):
        return self.env['connect.channel']._map_twilio_params({
            'CallSid': 'CAextentest',
            'Caller': caller,
            'Called': called,
            'To': called,
            'Direction': 'outbound-api',
            'CallStatus': 'in-progress',
        })

    def test_known_exten_loses_the_plus(self):
        self.assertEqual(
            self._map('+' + self.number)['caller'], self.number)

    def test_plain_exten_is_untouched(self):
        self.assertEqual(self._map(self.number)['caller'], self.number)

    def test_unknown_short_number_keeps_the_plus(self):
        self.assertEqual(
            self._map('+' + self.unknown_number)['caller'],
            '+' + self.unknown_number)

    def test_real_phone_number_keeps_the_plus(self):
        self.assertEqual(
            self._map('+19789814066')['caller'], '+19789814066')

    def test_client_uri_is_untouched(self):
        caller = 'client:admin@test.sip.twilio.com'
        self.assertEqual(self._map(caller)['caller'], caller)

    def test_called_exten_loses_the_plus(self):
        self.assertEqual(
            self._map('+19789814066', '+' + self.number)['called'],
            self.number)
