# -*- coding: utf-8 -*-
import json
from unittest.mock import patch

from odoo.tests import tagged

from .common import BirdTestCommon, FakeResponse

# Live item of GET /v1/sms/templates (trimmed).
SMS_TEMPLATE_ITEM = {
    'id': 'smt_6w8134jzjbadbteeca4p9e0dtm',
    'name': 'bird_otp_verification',
    'description': 'One-time passcode verification',
    'body': '{{ code }} is your verification code. Do not share it.',
    'category': 'authentication',
    'status': 'active',
    'scope': 'system',
    'available_languages': ['en'],
    'variables': [{'constraint': '4-8 digits', 'key': 'code',
                   'required': True, 'type': 'code'}],
}

# Live item of GET /v1/whatsapp/templates (trimmed).
WA_TEMPLATE_ITEM = {
    'category': 'authentication',
    'components': [
        {'example_parameters': [{'text': '123456', 'type': 'text'}],
         'text': '*{{1}}* is your verification code. For your security, '
                 'do not share this code.',
         'type': 'body'},
        {'buttons': [{'text': 'Copy code', 'type': 'url',
                      'url': 'https://example.com/{{1}}'}],
         'type': 'buttons'},
    ],
    'language': 'en',
    'name': 'bird_otp',
    'scope': 'system',
    'status': 'approved',
}


@tagged('at_install', '-post_install')
class TestBirdTemplates(BirdTestCommon):

    def test_map_sms_template(self):
        values = self.env['connect.bird.message_template'] \
            ._map_remote_sms_template(SMS_TEMPLATE_ITEM)
        self.assertEqual(values['sid'], 'smt_6w8134jzjbadbteeca4p9e0dtm')
        self.assertEqual(values['product'], 'sms')
        self.assertEqual(values['name'], 'bird_otp_verification')
        self.assertEqual(values['locale'], 'en')
        self.assertEqual(values['status'], 'active')
        self.assertEqual(
            values['body_preview'],
            '{{ code }} is your verification code. Do not share it.')
        self.assertEqual(
            json.loads(values['variables'])[0]['key'], 'code')

    def test_map_whatsapp_template(self):
        values = self.env['connect.bird.message_template'] \
            ._map_remote_whatsapp_template(WA_TEMPLATE_ITEM)
        self.assertEqual(values['sid'], 'wa:bird_otp:en')
        self.assertEqual(values['product'], 'whatsapp')
        self.assertEqual(values['name'], 'bird_otp')
        self.assertEqual(values['locale'], 'en')
        self.assertEqual(values['status'], 'approved')
        self.assertIn('verification code', values['body_preview'])
        # Positional {{1}} placeholder becomes a '1' variable key.
        self.assertEqual(
            [v['key'] for v in json.loads(values['variables'])], ['1'])

    def test_sync_both_products(self):
        pages = {
            '/sms/templates': {'data': [SMS_TEMPLATE_ITEM]},
            '/whatsapp/templates': {'data': [WA_TEMPLATE_ITEM]},
        }

        def fake_request(method, url, json=None, params=None, headers=None,
                         timeout=None):
            for path, page in pages.items():
                if url.endswith('/v1' + path):
                    return FakeResponse(200, page)
            return FakeResponse(404, {'error': {'message': 'not found'}},
                                content=b'x')

        with patch('odoo.addons.connect_bird.models.settings.httpx.request',
                   side_effect=fake_request):
            self.env['connect.bird.message_template'].sync()
        templates = self.env['connect.bird.message_template'].search([])
        self.assertEqual(len(templates), 2)
        self.assertEqual(set(templates.mapped('product')),
                         {'sms', 'whatsapp'})
        wa = templates.filtered(lambda t: t.product == 'whatsapp')
        self.assertEqual(wa.get_variable_keys(), ['1'])
