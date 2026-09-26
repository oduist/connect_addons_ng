# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class TestSettingsClient(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Settings = self.env['connect.settings']
        self.settings = self.Settings.search([], limit=1)
        if not self.settings:
            self.settings = self.Settings.create({})
        self.settings.with_context(skip_protected_fields=True).sudo().write({
            'account_sid': 'AC_TEST_ACCOUNT_SID',
            'api_key': 'a' * 64,
            'voiceml_base_url': 'https://voiceml.example.com',
        })

    def test_get_client_base_url(self):
        import voiceml
        client = self.Settings.get_client()
        self.assertIsInstance(client, voiceml.Client)
        self.assertEqual(client.base_url, 'https://voiceml.example.com')

    def test_get_media_auth_own_host(self):
        auth = self.Settings.get_media_auth(
            'https://voiceml.example.com/2010-04-01/Accounts/AC../Recordings/RE123.wav')
        self.assertEqual(
            auth,
            ('AC_TEST_ACCOUNT_SID', 'a' * 64),
        )

    def test_get_media_auth_foreign_host(self):
        auth = self.Settings.get_media_auth('https://bucket.s3.amazonaws.com/rec.wav')
        self.assertIsNone(auth)
