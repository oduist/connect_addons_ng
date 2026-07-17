# -*- coding: utf-8 -*-
"""User TTS prompt rendering: language/voice Say attributes (ADR-037)."""
from odoo.tests import tagged
from twilio.twiml.voice_response import VoiceResponse

from .common import TwilioTestCommon


@tagged('at_install', '-post_install')
class TestTwilioUserPrompts(TwilioTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls._create_connect_user(
            'tw_prompts',
            greeting_message='Welcome to my line',
            voicemail_prompt='Leave a message for {{ user.name }}.',
        )

    def test_greeting_default_language_and_voice(self):
        response = VoiceResponse()
        self.user.get_greeting_message(response)
        xml = str(response)
        self.assertIn('language="en-US"', xml)
        self.assertIn('voice="Woman"', xml)
        self.assertIn('Welcome to my line', xml)

    def test_voicemail_prompt_custom_language_and_voice(self):
        self.user.write({'language': 'de-DE', 'voice': 'Polly.Marlene'})
        response = VoiceResponse()
        self.user.get_voicemail_prompt(response)
        xml = str(response)
        self.assertIn('language="de-DE"', xml)
        self.assertIn('voice="Polly.Marlene"', xml)
        self.assertIn('Leave a message for', xml)
