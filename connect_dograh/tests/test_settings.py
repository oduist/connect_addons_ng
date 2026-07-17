# -*- coding: utf-8 -*-
"""Tests for the Dograh settings: URL normalization, health check and
service-token validation."""
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import DograhTestCommon, make_response


@tagged('post_install', '-at_install', 'connect_dograh')
class TestDograhSettings(DograhTestCommon):

    def _record(self):
        return self.settings.search([], limit=1)

    def test_api_url_normalization(self):
        self.settings.set_param('dograh_api_url', 'dograh.example.com/')
        self.assertEqual(self.settings.get_dograh_api_url(),
                         'https://dograh.example.com')
        self.settings.set_param('dograh_api_url',
                                'http://dograh.local:8000///')
        self.assertEqual(self.settings.get_dograh_api_url(),
                         'http://dograh.local:8000')
        self.settings.set_param('dograh_api_url', False)
        self.assertEqual(self.settings.get_dograh_api_url(), '')

    def test_service_token_default_generated(self):
        token = self.settings.get_param('dograh_service_token')
        self.assertTrue(token)
        self.assertGreaterEqual(len(token), 24)

    def test_weak_display_token_rejected(self):
        record = self._record()
        with self.assertRaises(ValidationError):
            record.write({'display_dograh_service_token': 'short'})

    def test_status_up(self):
        record = self._record()
        with patch('odoo.addons.connect_dograh.models.settings'
                   '.requests.get') as get:
            get.return_value = make_response(200, {'version': '1.41.0',
                                                   'status': 'ok'})
            record.check_dograh_status()
        self.assertEqual(record.dograh_status, 'UP 1.41.0')
        args, kwargs = get.call_args
        self.assertEqual(args[0],
                         'https://dograh.example.com/api/v1/health')

    def test_status_down(self):
        record = self._record()
        with patch('odoo.addons.connect_dograh.models.settings'
                   '.requests.get') as get:
            get.side_effect = Exception('boom')
            record.check_dograh_status()
        self.assertEqual(record.dograh_status, 'DOWN')

    def test_status_not_configured(self):
        self.settings.set_param('dograh_api_url', False)
        record = self._record()
        record.check_dograh_status()
        self.assertEqual(record.dograh_status, 'NOT CONFIGURED')
