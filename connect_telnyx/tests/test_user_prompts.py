# -*- coding: utf-8 -*-
"""User TTS prompt rendering: language/voice Say attributes (ADR-037)."""
from odoo.tests import tagged

from ..models.texml_response import VoiceResponse
from .common import TelnyxTestCommon


@tagged('at_install', '-post_install')
class TestTelnyxUserPrompts(TelnyxTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['connect.settings'].sudo().set_param(
            'telnyx_system_voice', 'Polly.Joanna')
        cls.user = cls._create_connect_user(
            'tx_prompts',
            greeting_message='Welcome to my line',
            voicemail_prompt='Leave a message for {{ user.name }}.',
        )

    def test_greeting_default_language_and_voice(self):
        response = VoiceResponse()
        self.user.get_telnyx_greeting_message(response)
        xml = str(response)
        self.assertIn('language="en-US"', xml)
        self.assertIn('voice="Polly.Joanna"', xml)
        self.assertIn('Welcome to my line', xml)

    def test_voicemail_prompt_custom_language_and_voice(self):
        self.user.write({'language': 'fr-FR', 'voice': 'Polly.Lea'})
        response = VoiceResponse()
        self.user.get_telnyx_voicemail_prompt(response)
        xml = str(response)
        self.assertIn('language="fr-FR"', xml)
        self.assertIn('voice="Polly.Lea"', xml)
        self.assertIn('Leave a message for', xml)
