# -*- coding: utf-8 -*-
"""Pure-function tests for the X-Twilio-Signature implementation.

Expected values are pinned against twilio-python's
``RequestValidator.compute_signature`` (twilio 9.x), so this proves the
stdlib reimplementation is byte-identical to what connect_twilio's own
webhook validation accepts.
"""

from odoo.tests.common import TransactionCase

from odoo.addons.connect_voiceml.models import webhook


class TestWebhookSignature(TransactionCase):

    def test_canonical_twilio_example(self):
        # Twilio's documented "Validating requests" example, verified against
        # twilio-python RequestValidator('12345').compute_signature(...).
        url = 'https://mycompany.com/myapp.php?foo=1&bar=2'
        params = {
            'CallSid': 'CA1234567890ABCDE',
            'Caller': '+12349013030',
            'Digits': '1234',
            'From': '+12349013030',
            'To': '+18005551212',
        }
        self.assertEqual(
            webhook.sign_request(url, params, '12345'),
            '0/KCTR6DLpKmkAf8muzZqo1nDgQ=',
        )

    def test_empty_value_is_not_skipped(self):
        # Twilio appends a bare key for an empty-string value; skipping it
        # would produce a different (wrong) signature.
        params = {'CallSid': 'CA1234567890ABCDE', 'Caller': '', 'Digits': '1234'}
        self.assertEqual(
            webhook.sign_request('https://mycompany.com/myapp.php', params, '12345'),
            '4yruHa3cfPVQoxHLp5lbjPe+9W0=',
        )

    def test_roundtrip_valid(self):
        url = 'https://example.com/voiceml/webhook/callstatus'
        params = {'CallSid': 'CAabc', 'CallStatus': 'completed'}
        sig = webhook.sign_request(url, params, 'secret')
        self.assertTrue(webhook.valid_request(url, params, sig, 'secret'))

    def test_tampered_signature_rejected(self):
        url = 'https://example.com/voiceml/webhook/callstatus'
        params = {'CallSid': 'CAabc'}
        self.assertFalse(webhook.valid_request(url, params, 'AAAA', 'secret'))
        self.assertFalse(webhook.valid_request(url, params, '', 'secret'))

    def test_port_tolerant(self):
        # Twilio's own signing is inconsistent about the port, so a signature
        # computed on the no-port URL validates against the with-port URL.
        no_port = 'https://example.com/voiceml/webhook/callstatus'
        sig = webhook.sign_request(no_port, {'Digits': '1234'}, '12345')
        self.assertTrue(webhook.valid_request(
            'https://example.com:8443/voiceml/webhook/callstatus',
            {'Digits': '1234'}, sig, '12345'))

    def test_normalize_url_scheme(self):
        self.assertEqual(
            webhook.normalize_url('http://example.com/x'),
            'https://example.com/x',
        )
