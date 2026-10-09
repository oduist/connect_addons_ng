# -*- coding: utf-8 -*-
"""Credentials used to fetch recording media through the Odoo proxy.

An unauthenticated fetch answers 403, the proxy turns that into an error
status, and the browser's audio element reports a 0-second recording — so
the credentials have to reach Twilio, and only Twilio.
"""
from odoo.tests import tagged

from .common import TwilioTestCommon

ACCOUNT_SID = 'ACmediatest'
AUTH_TOKEN = 'media_test_auth_token'


@tagged('at_install', '-post_install')
class TestRecordingMedia(TwilioTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.settings = cls.env['connect.settings'].sudo()
        cls.settings.set_param('account_sid', ACCOUNT_SID)
        cls.settings.set_param('auth_token', AUTH_TOKEN)

    def test_twilio_media_is_fetched_with_the_account_credentials(self):
        auth = self.settings.get_media_auth(
            'https://api.twilio.com/2010-04-01/Accounts/{}/Recordings/RE1'
            .format(ACCOUNT_SID))

        self.assertEqual(auth, (ACCOUNT_SID, AUTH_TOKEN))

    def test_external_storage_media_gets_no_twilio_credentials(self):
        """External Storage serves from a bucket: never send the auth token."""
        auth = self.settings.get_media_auth(
            'https://recordings.s3.eu-central-1.amazonaws.com/RE1')

        self.assertIsNone(auth)

    def test_a_lookalike_host_gets_no_credentials(self):
        auth = self.settings.get_media_auth(
            'https://api.twilio.com.evil.example/RE1')

        self.assertIsNone(auth)

    def test_no_credentials_configured_means_anonymous(self):
        self.settings.set_param('auth_token', False)

        auth = self.settings.get_media_auth(
            'https://api.twilio.com/2010-04-01/Recordings/RE1')

        self.assertIsNone(auth)
