# -*- coding: utf-8 -*-
import json
import time

from odoo.tests import HttpCase, tagged

from .common import bird_sign, TEST_SIGNING_SECRET


@tagged('post_install', '-at_install')
class TestBirdWebhookSignature(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Settings = cls.env['connect.settings'].sudo()
        Settings.set_param('bird_access_key', 'bk_eu1_testkey')
        Settings.set_param('bird_webhook_signing_key', TEST_SIGNING_SECRET)
        Settings.set_param('bird_verify_requests', True)
        cls.number = cls.env['connect.bird.number'].create({
            'sid': 'num-sig',
            'number': '+15550001',
            'name': 'Sig',
            'status': 'active',
            'capabilities': 'sms',
        })

    def _post(self, body, sign_with=TEST_SIGNING_SECRET, timestamp=None,
              webhook_id='wh-msg-1', headers=None):
        raw = json.dumps(body).encode()
        headers = dict(headers or {})
        headers['Content-Type'] = 'application/json'
        if sign_with:
            ts = timestamp or int(time.time())
            headers['webhook-id'] = webhook_id
            headers['webhook-timestamp'] = str(ts)
            headers['webhook-signature'] = bird_sign(
                webhook_id, ts, raw, sign_with)
        return self.url_open('/bird/webhook', data=raw, headers=headers)

    def _event(self, message_id):
        return {
            'type': 'sms.received',
            'timestamp': '2026-07-11T00:00:00Z',
            'data': {
                'sms_id': message_id,
                'from': '+31612345678',
                'to': '+15550001',
                'text': 'signed hello',
                'direction': 'inbound',
            },
        }

    def test_valid_signature_accepted_and_processed(self):
        res = self._post(self._event('sig-ok'))
        self.assertEqual(res.status_code, 200)
        message = self.env['connect.message'].search(
            [('bird_message_id', '=', 'sig-ok')])
        self.assertEqual(len(message), 1)
        self.assertEqual(message.body, 'signed hello')

    def test_missing_signature_rejected(self):
        res = self._post(self._event('sig-none'), sign_with=None)
        self.assertEqual(res.status_code, 401)
        self.assertFalse(self.env['connect.message'].search(
            [('bird_message_id', '=', 'sig-none')]))

    def test_wrong_secret_rejected(self):
        res = self._post(self._event('sig-bad'),
                         sign_with='whsec_d3Jvbmcta2V5')
        self.assertEqual(res.status_code, 401)

    def test_stale_timestamp_rejected(self):
        res = self._post(self._event('sig-old'),
                         timestamp=int(time.time()) - 3600)
        self.assertEqual(res.status_code, 401)

    def test_tampered_body_rejected(self):
        body = self._event('sig-tampered')
        raw = json.dumps(body).encode()
        ts = int(time.time())
        signature = bird_sign('wh-tamper', ts, raw)
        tampered = json.dumps(dict(body, type='sms.delivered')).encode()
        res = self.url_open('/bird/webhook', data=tampered, headers={
            'Content-Type': 'application/json',
            'webhook-id': 'wh-tamper',
            'webhook-timestamp': str(ts),
            'webhook-signature': signature,
        })
        self.assertEqual(res.status_code, 401)

    def test_multiple_signatures_header(self):
        # During secret rotation the header may carry several versioned
        # signatures; a valid one among them must be accepted.
        body = self._event('sig-multi')
        raw = json.dumps(body).encode()
        ts = int(time.time())
        good = bird_sign('wh-multi', ts, raw)
        res = self.url_open('/bird/webhook', data=raw, headers={
            'Content-Type': 'application/json',
            'webhook-id': 'wh-multi',
            'webhook-timestamp': str(ts),
            'webhook-signature': 'v1,Zm9vYmFy ' + good,
        })
        self.assertEqual(res.status_code, 200)

    def test_verification_bypass(self):
        self.env['connect.settings'].sudo().set_param(
            'bird_verify_requests', False)
        try:
            res = self._post(self._event('sig-bypass'), sign_with=None)
            self.assertEqual(res.status_code, 200)
            self.assertTrue(self.env['connect.message'].search(
                [('bird_message_id', '=', 'sig-bypass')]))
        finally:
            self.env['connect.settings'].sudo().set_param(
                'bird_verify_requests', True)
