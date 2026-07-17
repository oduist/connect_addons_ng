# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.tests import tagged
from odoo.exceptions import ValidationError

from .common import BirdTestCommon, FakeResponse


@tagged('at_install', '-post_install')
class TestBirdSettings(BirdTestCommon):

    def _patch_httpx(self, response):
        return patch(
            'odoo.addons.connect_bird.models.settings.httpx.request',
            return_value=response)

    def test_bird_request_url_and_headers(self):
        with self._patch_httpx(FakeResponse(200, {'ok': True})) as req:
            res = self.env['connect.settings'].bird_request('GET', '/numbers')
        self.assertEqual(res, {'ok': True})
        args, kwargs = req.call_args
        self.assertEqual(args[0], 'GET')
        # Region eu1 is inferred from the bk_eu1_ key prefix.
        self.assertEqual(
            args[1], 'https://eu1.platform.bird.com/v1/numbers')
        self.assertEqual(
            kwargs['headers']['Authorization'], 'Bearer bk_eu1_testkey')

    def test_bird_request_error_raises(self):
        response = FakeResponse(
            403, {'code': 'Forbidden', 'message': 'Missing scope'},
            content=b'x')
        with self._patch_httpx(response):
            with self.assertRaises(ValidationError):
                self.env['connect.settings'].bird_request('POST', '/numbers')

    def test_bird_request_nested_error_details(self):
        # Live platform error envelope: {"error": {message, details[]}}.
        response = FakeResponse(422, {'error': {
            'type': 'validation_error',
            'code': 'E01001',
            'message': 'Request has 1 validation error.',
            'details': [{'param': 'body', 'message': "missing property 'to'"}],
        }}, content=b'x')
        with self._patch_httpx(response):
            with self.assertRaises(ValidationError) as cm:
                self.env['connect.settings'].bird_request(
                    'POST', '/sms/messages')
        self.assertIn("missing property 'to'", str(cm.exception))

    def test_bird_request_error_silent(self):
        response = FakeResponse(500, ValueError('no json'), content=b'oops')
        with self._patch_httpx(response):
            res = self.env['connect.settings'].bird_request(
                'POST', '/numbers', raise_exc=False)
        self.assertIs(res, False)

    def test_bird_request_requires_credentials(self):
        self.env['connect.settings'].sudo().set_param('bird_access_key', False)
        with self.assertRaises(ValidationError):
            self.env['connect.settings'].bird_request('GET', '/numbers')

    def test_base_url_override(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'connect.bird_api_url', 'https://mock.example.com')
        try:
            with self._patch_httpx(FakeResponse(200, {})) as req:
                self.env['connect.settings'].bird_request('GET', '/numbers')
            self.assertEqual(
                req.call_args[0][1], 'https://mock.example.com/v1/numbers')
        finally:
            self.env['ir.config_parameter'].sudo().set_param(
                'connect.bird_api_url', '')

    def test_bird_paginate(self):
        pages = [
            {'data': [{'id': 'a'}, {'id': 'b'}], 'next_cursor': 'cur-1'},
            {'data': [{'id': 'c'}], 'next_cursor': None},
        ]
        calls = []

        def fake_request(method, url, json=None, params=None, headers=None,
                         timeout=None):
            calls.append(dict(params or {}))
            return FakeResponse(200, pages[len(calls) - 1])

        with patch('odoo.addons.connect_bird.models.settings.httpx.request',
                   side_effect=fake_request):
            items = list(self.env['connect.settings'].bird_paginate('/numbers'))
        self.assertEqual([i['id'] for i in items], ['a', 'b', 'c'])
        self.assertEqual(calls[1].get('starting_after'), 'cur-1')

    def test_protected_fields_masking(self):
        rec = self.settings
        rec.write({'display_bird_access_key': 'secret-key-1'})
        self.assertEqual(rec.bird_access_key, 'secret-key-1')
        self.assertEqual(rec.display_bird_access_key, '*' * len('secret-key-1'))
