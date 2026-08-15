# -*- coding: utf-8 -*-
import base64
import time
from urllib.parse import urlencode

from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestTelnyxWebhookSignature(HttpCase):
    """Telnyx signs the raw request body. TeXML webhooks are form-encoded
    and Odoo parses the form before the controller runs, so the signature
    must be checked against the body rebuilt from the parsed form."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from nacl.signing import SigningKey
        cls.signing_key = SigningKey.generate()
        settings = cls.env['connect.settings'].sudo()
        settings.set_param('telnyx_auto_sync', False)
        settings.set_param('telnyx_verify_requests', True)
        settings.set_param('telnyx_public_key', base64.b64encode(
            bytes(cls.signing_key.verify_key)).decode())
        cls.texml = cls.env['connect.telnyx.texml'].with_context(
            skip_telnyx_sync=True).create({
                'name': 'Signed Reject',
                'code_type': 'texml',
                'texml': '<Response><Reject /></Response>',
                'sid': 'texml-signed',
            })

    def _post(self, params, sign=True):
        body = urlencode(params)
        timestamp = str(int(time.time()))
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        if sign:
            signature = self.signing_key.sign(
                '{}|{}'.format(timestamp, body).encode()).signature
            headers['telnyx-timestamp'] = timestamp
            headers['telnyx-signature-ed25519'] = base64.b64encode(
                signature).decode()
        return self.url_open(
            '/telnyx/webhook/texml/{}'.format(self.texml.id),
            data=body, headers=headers)

    def test_signed_form_webhook_is_accepted(self):
        response = self._post([
            ('To', '+15550001111'), ('From', '+15550002222'),
            ('CallSid', 'signed-call'), ('CallStatus', 'initiated')])
        self.assertEqual(response.status_code, 200)
        self.assertIn('<Reject', response.text)

    def test_unsigned_form_webhook_is_rejected(self):
        response = self._post([('To', '+15550001111')], sign=False)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Invalid Telnyx request', response.text)

    def test_rejected_call_status_returns_an_empty_body(self):
        """A handler must return a response body; returning False made
        Odoo answer 500."""
        response = self.url_open(
            '/telnyx/webhook/callstatus',
            data=urlencode([('CallSid', 'unsigned')]),
            headers={'Content-Type': 'application/x-www-form-urlencoded'})
        self.assertEqual(response.status_code, 200)
