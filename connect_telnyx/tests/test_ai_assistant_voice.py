# -*- coding: utf-8 -*-
import json
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged

from ..models.settings import Settings
from .common import TelnyxTestCommon

CATALOG = [
    {
        'id': 'Telnyx.Ultra.11111111-2222-3333-4444-555555555555',
        'name': 'Callie',
        'provider': 'telnyx',
        'language': 'en-US',
        'gender': 'Female',
    },
    {
        # Telnyx reports no language for some account-scoped voices.
        'id': 'Telnyx.Ultra.99999999-8888-7777-6666-555555555555',
        'name': 'Cloned Anna',
        'provider': 'telnyx',
        'language': '',
        'gender': 'Female',
    },
    {
        'id': 'AWS.Polly.Joanna-Neural',
        'name': 'Joanna',
        'provider': 'aws',
        'language': 'en-US',
        'gender': 'Female',
    },
]


@tagged('at_install', '-post_install')
class TestTelnyxAssistantVoice(TelnyxTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['connect.settings'].sudo().set_param(
            'telnyx_tts_voices', json.dumps(CATALOG))
        cls.Assistant = cls.env['connect.telnyx.ai_assistant']
        cls.connect_admin = new_test_user(
            cls.env, login='telnyx-voice-admin',
            groups='base.group_user,connect.group_admin')

    def _create_assistant(self, **vals):
        values = {'name': 'Voice Assistant'}
        values.update(vals)
        return self.Assistant.create(values)

    def test_assistant_options_exclude_the_basic_texml_voices(self):
        assistant_ids = [
            option['value'] for option in self.Assistant.telnyx_get_voice_options(
                'en-US', 'basic')
        ]
        settings_ids = [
            option['value']
            for option in self.env['connect.settings'].telnyx_get_voice_options(
                'en-US', 'basic')
        ]

        self.assertEqual(assistant_ids, [])
        self.assertIn('man', settings_ids)

    def test_a_voice_without_language_matches_any_filter(self):
        options = [
            option['value'] for option in self.Assistant.telnyx_get_voice_options(
                'pl-PL', 'telnyx')
        ]

        self.assertEqual(
            options, ['Telnyx.Ultra.99999999-8888-7777-6666-555555555555'])

    def test_voice_label_uses_the_catalog_name(self):
        assistant = self._create_assistant(voice=CATALOG[0]['id'])

        self.assertEqual(assistant.voice_label, 'Callie')

    def test_voice_label_falls_back_to_the_raw_identifier(self):
        assistant = self._create_assistant(voice='Telnyx.Ultra.unknown')

        self.assertEqual(assistant.voice_label, 'Telnyx.Ultra.unknown')

    def test_filters_follow_the_selected_voice(self):
        assistant = self._create_assistant(voice='AWS.Polly.Joanna-Neural')

        self.assertEqual(assistant.voice_language, 'en-US')
        self.assertEqual(assistant.voice_provider, 'aws')

        assistant.voice = CATALOG[0]['id']

        self.assertEqual(assistant.voice_provider, 'telnyx')

    def test_filters_survive_a_voice_without_language(self):
        assistant = self._create_assistant(
            voice_language='pl-PL', voice=CATALOG[1]['id'])

        self.assertEqual(assistant.voice_language, 'pl-PL')
        self.assertEqual(assistant.voice_provider, 'telnyx')

    def test_changing_a_filter_clears_an_incompatible_voice(self):
        assistant = self.Assistant.new({
            'name': 'Voice Assistant',
            'voice': 'AWS.Polly.Joanna-Neural',
            'voice_language': 'en-US',
            'voice_provider': 'aws',
        })

        assistant.voice_provider = 'telnyx'
        assistant._onchange_voice_filters()

        self.assertFalse(assistant.voice)

    def test_expressive_mode_is_offered_for_ultra_voices_only(self):
        ultra = self._create_assistant(voice=CATALOG[0]['id'])
        polly = self._create_assistant(voice='AWS.Polly.Joanna-Neural')

        self.assertTrue(ultra.voice_is_expressive)
        self.assertFalse(polly.voice_is_expressive)

    def test_leaving_an_ultra_voice_disables_expressive_mode(self):
        assistant = self.Assistant.new({
            'name': 'Voice Assistant',
            'voice': CATALOG[0]['id'],
            'expressive_mode': True,
        })

        assistant.voice = 'AWS.Polly.Joanna-Neural'
        assistant._onchange_voice_expression()

        self.assertFalse(assistant.expressive_mode)

    def test_unknown_remote_language_boost_is_ignored(self):
        vals = self.Assistant._remote_values({
            'id': 'assistant-1',
            'voice_settings': {
                'voice': 'AWS.Polly.Joanna-Neural',
                'language_boost': 'Klingon',
            },
        })

        self.assertFalse(vals['language_boost'])

        vals = self.Assistant._remote_values({
            'id': 'assistant-1',
            'voice_settings': {'language_boost': 'Polish'},
        })

        self.assertEqual(vals['language_boost'], 'Polish')

    def test_voice_preview_sends_the_speed_of_the_matching_provider(self):
        calls = []

        def fake_request(settings, method, path, payload=None, **kwargs):
            calls.append((method, path, payload))
            return {'base64_audio': 'QUJD'}

        Assistant = self.Assistant.with_user(self.connect_admin)
        with patch.object(
                Settings, 'telnyx_api_request', autospec=True,
                side_effect=fake_request):
            telnyx_sample = Assistant.telnyx_preview_voice(
                CATALOG[0]['id'], 1.2, 'Hello there')
            Assistant.telnyx_preview_voice(
                'AWS.Polly.Joanna-Neural', 1.2, 'Hello there')

        self.assertEqual(telnyx_sample['audio'], 'QUJD')
        self.assertEqual(calls[0][1], 'text-to-speech/speech')
        self.assertEqual(calls[0][2]['output_type'], 'base64_output')
        self.assertEqual(calls[0][2]['text'], 'Hello there')
        self.assertEqual(calls[0][2]['telnyx'], {'voice_speed': 1.2})
        # AWS has no speed parameter; sending one would fail the request.
        self.assertNotIn('aws', calls[1][2])

    def test_voice_preview_replaces_a_greeting_with_variables(self):
        calls = []

        def fake_request(settings, method, path, payload=None, **kwargs):
            calls.append(payload)
            return {'base64_audio': 'QUJD'}

        with patch.object(
                Settings, 'telnyx_api_request', autospec=True,
                side_effect=fake_request):
            self.Assistant.with_user(self.connect_admin).telnyx_preview_voice(
                CATALOG[0]['id'], 1.0, 'Hello, {{customer_name}}!')

        self.assertNotIn('{{', calls[0]['text'])

    def test_voice_preview_is_restricted_to_administrators(self):
        user = new_test_user(
            self.env, login='telnyx-voice-user', groups='connect.group_user')

        with self.assertRaises(AccessError):
            self.Assistant.with_user(user).telnyx_preview_voice(
                CATALOG[0]['id'])

    def test_voice_catalog_lookups_work_without_settings_access(self):
        user = new_test_user(
            self.env, login='telnyx-voice-reader', groups='connect.group_user')
        Assistant = self.Assistant.with_user(user)

        label = Assistant.telnyx_get_voice_label(CATALOG[0]['id'])
        options = Assistant.telnyx_get_voice_options('en-US', 'telnyx')

        self.assertEqual(label['label'], 'Callie')
        # The language-less clone matches every language filter.
        self.assertEqual([option['value'] for option in options],
                         [CATALOG[0]['id'], CATALOG[1]['id']])
