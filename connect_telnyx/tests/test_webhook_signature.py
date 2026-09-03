# -*- coding: utf-8 -*-
import base64
import time
from urllib.parse import urlencode

from odoo.tests import HttpCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestTelnyxWebhookSignature(HttpCase):
    """Telnyx signatures are checked against the original request bytes."""

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
        # api_url is a non-stored compute; write the backing config
        # parameter so the value survives cache invalidation.
        cls.env['ir.config_parameter'].sudo().set_param(
            'connect.api_url', 'https://odoo.example.test/')
        cls.texml = cls.env['connect.telnyx.texml'].with_context(
            install_mode=True).create({
                'name': 'Signed Reject',
                'code_type': 'texml',
                'texml': '<Response><Reject /></Response>',
                'sid': 'texml-signed',
            })
        odoo_user = new_test_user(cls.env, login='telnyx_signature_user')
        cls.connect_user = cls.env['connect.user'].with_context(
            no_clear_cache=True, no_telnyx_create=True).create({
                'user': odoo_user.id,
            })

    def _post_body(self, path, body, sign=True):
        body = body.encode() if isinstance(body, str) else body
        timestamp = str(int(time.time()))
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        if sign:
            signature = self.signing_key.sign(
                timestamp.encode() + b'|' + body).signature
            headers['telnyx-timestamp'] = timestamp
            headers['telnyx-signature-ed25519'] = base64.b64encode(
                signature).decode()
        return self.url_open(path, data=body, headers=headers)

    def _post(self, params, sign=True):
        return self._post_body(
            '/telnyx/webhook/texml/{}'.format(self.texml.id),
            urlencode(params), sign=sign)

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

    def test_signed_complex_form_uses_original_raw_body(self):
        parts = [
            'AccountSid=0c1d2e3f-4a5b-678c-9d0e-1f2a3b4c5d6e',
            'ApiVersion=2010-04-01',
            'CallSid=v3%3Aparent-leg-0123456789abcdef',
            'DialCallSid=v3%3Asip-leg-fedcba9876543210',
            'CallStatus=completed',
            'DialCallStatus=completed',
            'DialCallDuration=9',
            'DialSipResponseCode=200',
            'Direction=inbound',
            'From=%2B15551230000',
            'To=sip%3A101%40example.sip.telnyx.com',
            'CallerName=External+Caller',
            'SipHeader_X-Telnyx-Disconnect-Reason=normal%20clearing',
            (
                'RecordingUrl=https%3A%2F%2Fexample.test%2Frecordings%2F'
                'call.mp3%3FX-Amz-Algorithm%3DAWS4-HMAC-SHA256'
                '%26X-Amz-Credential%3Dtest%252F20260816%252Fus-east-1'
                '%252Fs3%252Faws4_request%26X-Amz-Signature%3D' +
                'a' * 1400
            ),
        ]
        body = '&'.join(parts)
        self.assertEqual(len(body.encode()), 1998)
        response = self._post_body(
            '/telnyx/webhook/texml/{}'.format(self.texml.id),
            body,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('<Reject', response.text)
        self.assertNotIn('Invalid Telnyx request', response.text)

    def test_invalid_call_action_signatures_hang_up_silently(self):
        paths = [
            '/telnyx/webhook/connect.user/call_action/{}'.format(
                self.connect_user.id),
            '/telnyx/webhook/callaction',
        ]
        for path in paths:
            with self.subTest(path=path):
                response = self._post_body(
                    path, 'CallStatus=completed', sign=False)
                self.assertEqual(response.status_code, 200)
                self.assertIn('<Hangup', response.text)
                self.assertNotIn('<Say', response.text)
                self.assertNotIn('Invalid Telnyx request', response.text)

    def test_rejected_call_status_returns_an_empty_body(self):
        """A handler must return a response body; returning False made
        Odoo answer 500."""
        response = self.url_open(
            '/telnyx/webhook/callstatus',
            data=urlencode([('CallSid', 'unsigned')]),
            headers={'Content-Type': 'application/x-www-form-urlencoded'})
        self.assertEqual(response.status_code, 200)
