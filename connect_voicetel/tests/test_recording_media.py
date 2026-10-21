# -*- coding: utf-8 -*-
"""Credentials used to fetch recording media through the Odoo proxy.

VoiceML serves the WAV with HTTP Basic auth; once the tenant's own bucket
took it, the API redirects to a presigned S3 URL that must never receive
the API key.
"""
from odoo.tests import tagged

from .common import VoiceTelTestCommon

ACCOUNT_SID = 'ACmediatest'
API_KEY = 'media_test_api_key'


@tagged('at_install', '-post_install')
class TestRecordingMedia(VoiceTelTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.settings = cls.env['connect.settings'].sudo()
        cls.settings.set_param('voicetel_account_sid', ACCOUNT_SID)
        cls.settings.set_param('voicetel_api_key', API_KEY)
        cls.settings.set_param('voicetel_api_host', 'voiceml.voicetel.com')

    def test_voiceml_media_is_fetched_with_the_account_credentials(self):
        auth = self.settings.get_media_auth(
            'https://voiceml.voicetel.com/2010-04-01/Accounts/{}/Recordings/RE1'
            .format(ACCOUNT_SID))

        self.assertEqual(auth, (ACCOUNT_SID, API_KEY))

    def test_the_configured_host_is_the_one_trusted(self):
        self.settings.set_param('voicetel_api_host', 'voiceml.example.net')

        self.assertEqual(
            self.settings.get_media_auth(
                'https://voiceml.example.net/2010-04-01/Recordings/RE1'),
            (ACCOUNT_SID, API_KEY))
        self.assertIsNone(self.settings.get_media_auth(
            'https://voiceml.voicetel.com/2010-04-01/Recordings/RE1'))

    def test_bucket_media_gets_no_voiceml_credentials(self):
        auth = self.settings.get_media_auth(
            'https://recordings.s3.us-east-1.amazonaws.com/RE1')

        self.assertIsNone(auth)

    def test_a_lookalike_host_gets_no_credentials(self):
        auth = self.settings.get_media_auth(
            'https://voiceml.voicetel.com.evil.example/RE1')

        self.assertIsNone(auth)

    def test_no_credentials_configured_means_anonymous(self):
        self.settings.set_param('voicetel_api_key', False)

        auth = self.settings.get_media_auth(
            'https://voiceml.voicetel.com/2010-04-01/Recordings/RE1')

        self.assertIsNone(auth)

    def test_relative_recording_url_is_completed_with_the_host(self):
        url = self.env['connect.recording']._voicetel_media_url(
            '/2010-04-01/Accounts/AC1/Recordings/RE1')

        self.assertEqual(
            url, 'https://voiceml.voicetel.com/2010-04-01/Accounts/AC1/Recordings/RE1')
