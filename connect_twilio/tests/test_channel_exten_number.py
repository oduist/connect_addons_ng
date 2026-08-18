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
        cls.exten = cls.env['connect.twilio.exten'].create({'number': '100'})

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
        self.assertEqual(self._map('+100')['caller'], '100')

    def test_plain_exten_is_untouched(self):
        self.assertEqual(self._map('100')['caller'], '100')

    def test_unknown_short_number_keeps_the_plus(self):
        self.assertEqual(self._map('+199')['caller'], '+199')

    def test_real_phone_number_keeps_the_plus(self):
        self.assertEqual(
            self._map('+19789814066')['caller'], '+19789814066')

    def test_client_uri_is_untouched(self):
        caller = 'client:admin@test.sip.twilio.com'
        self.assertEqual(self._map(caller)['caller'], caller)

    def test_called_exten_loses_the_plus(self):
        self.assertEqual(self._map('+19789814066', '+100')['called'], '100')
