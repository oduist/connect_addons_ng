# -*- coding: utf-8 -*-
"""connect.settings Infobip extension tests: API client assembly, secret
masking, webhook token/URLs (ADR-036)."""
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import InfobipTestCommon, make_response

REQUESTS_PATH = 'odoo.addons.connect_infobip.models.settings.requests.request'


@tagged('at_install', '-post_install')
class TestInfobipSettings(InfobipTestCommon):

    def test_api_request_headers_and_url(self):
        with patch(REQUESTS_PATH) as mock_request:
            mock_request.return_value = make_response(
                json_data={'ok': True}, content=b'{"ok": true}')
            result = self.settings.infobip_api_request(
                'GET', '/calls/1/calls/abc')
        self.assertEqual(result, {'ok': True})
        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], 'GET')
        self.assertEqual(
            args[1], 'https://test.api.infobip.com/calls/1/calls/abc')
        self.assertEqual(
            kwargs['headers']['Authorization'], 'App TESTKEY123')

    def test_api_error_does_not_leak_key(self):
        with patch(REQUESTS_PATH) as mock_request:
            mock_request.return_value = make_response(
                status_code=401,
                json_data={'requestError': {'serviceException': {
                    'text': 'Invalid login details'}}},
                content=b'x')
            with self.assertRaises(ValidationError) as err:
                self.settings.infobip_api_request('GET', '/numbers/1/numbers')
        message = str(err.exception)
        self.assertIn('401', message)
        self.assertIn('Invalid login details', message)
        self.assertNotIn('TESTKEY123', message)

    def test_api_request_requires_base_url(self):
        self.settings.set_param('infobip_base_url', False)
        with self.assertRaises(ValidationError):
            self.settings.infobip_api_request('GET', '/numbers/1/numbers')

    def test_api_key_masking(self):
        settings = self.env['connect.settings'].sudo().search([], limit=1)
        settings.write({'display_infobip_api_key': 'SECRET99'})
        self.assertEqual(settings.infobip_api_key, 'SECRET99')
        self.assertEqual(settings.display_infobip_api_key, '*' * len('SECRET99'))

    def test_webhook_token_default(self):
        token = self.settings.get_param('infobip_webhook_token')
        self.assertTrue(token)
        self.assertGreater(len(token), 20)

    def test_webhook_url_carries_token(self):
        self.settings.set_param('api_url', 'https://odoo.example.com/')
        url = self.settings.get_infobip_webhook_url('voice/event')
        token = self.settings.get_param('infobip_webhook_token')
        self.assertIn('/infobip/webhook/voice/event', url)
        self.assertIn('token={}'.format(token), url)

    def test_originate_provider_registered(self):
        values = self.env['connect.user']._fields[
            'originate_provider'].get_values(self.env)
        self.assertIn('infobip', values)
