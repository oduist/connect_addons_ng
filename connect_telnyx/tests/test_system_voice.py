# -*- coding: utf-8 -*-
import json
from unittest.mock import patch

from odoo.tests import tagged

from ..models.settings import Settings
from ..models.texml_response import VoiceResponse
from .common import TelnyxTestCommon


@tagged('at_install', '-post_install')
class TestTelnyxSystemVoice(TelnyxTestCommon):

    def test_system_voice_is_added_to_missing_say_only(self):
        settings = self.env['connect.settings'].sudo()
        settings.set_param('telnyx_system_voice', 'woman')

        xml = settings.telnyx_apply_system_voice(
            '<Response><Say>Hello</Say><Gather>'
            '<Say voice="Polly.Lea">Bonjour</Say></Gather></Response>')

        self.assertIn('<Say voice="woman">Hello</Say>', xml)
        self.assertIn('<Say voice="Polly.Lea">Bonjour</Say>', xml)

    def test_non_xml_output_is_unchanged(self):
        content = 'not valid TeXML'
        self.assertEqual(
            self.env['connect.settings'].telnyx_apply_system_voice(content),
            content,
        )

    def test_voice_catalog_accepts_id_and_voice_id(self):
        response = {
            'voices': [
                {
                    'id': 'Telnyx.NaturalHD.astra',
                    'name': 'Astra',
                    'provider': 'telnyx',
                    'language': 'en-US',
                    'gender': 'female',
                },
                {
                    'voice_id': 'AWS.Polly.Marlene-Neural',
                    'name': 'Marlene',
                    'provider': 'aws',
                    'language': 'de-DE',
                    'gender': 'female',
                },
            ],
        }
        with patch.object(
                Settings, 'telnyx_api_request', autospec=True,
                return_value=response):
            self.env['connect.settings']._sync_telnyx_tts_voices()

        cached = json.loads(self.env['connect.settings'].sudo().get_param(
            'telnyx_tts_voices'))
        self.assertEqual(
            [voice['id'] for voice in cached],
            ['Telnyx.NaturalHD.astra', 'AWS.Polly.Marlene-Neural'],
        )
        settings = self.env['connect.settings']
        languages = dict(settings._get_telnyx_voice_language_selection())
        providers = dict(settings._get_telnyx_voice_provider_selection())
        self.assertEqual(languages['en-US'], 'English (United States) (en-US)')
        self.assertEqual(languages['de-DE'], 'German (Germany) (de-DE)')
        self.assertEqual(providers['aws'], 'Amazon Web Services')
        self.assertEqual(providers['telnyx'], 'Telnyx')

        telnyx_options = settings.telnyx_get_voice_options(
            'en-US', 'telnyx', 'astra')
        aws_options = settings.telnyx_get_voice_options(
            'de-DE', 'aws', 'female')
        self.assertEqual(telnyx_options, [{
            'value': 'Telnyx.NaturalHD.astra',
            'label': 'Astra',
            'details': 'female - Telnyx.NaturalHD.astra',
        }])
        self.assertEqual(aws_options[0]['value'], 'AWS.Polly.Marlene-Neural')

    def test_voice_options_are_filtered_and_bounded(self):
        voices = [
            {
                'id': 'Telnyx.NaturalHD.voice-{}'.format(index),
                'name': 'Voice {}'.format(index),
                'provider': 'telnyx',
                'language': 'pl-PL',
                'gender': 'Female',
            }
            for index in range(5)
        ]
        voices.append({
            'id': 'AWS.Polly.Ola-Neural',
            'name': 'Ola',
            'provider': 'aws',
            'language': 'pl-PL',
            'gender': 'Female',
        })
        settings = self.env['connect.settings'].sudo()
        settings.set_param('telnyx_tts_voices', json.dumps(voices))

        options = settings.telnyx_get_voice_options(
            'pl-PL', 'telnyx', 'voice', limit=2)

        self.assertEqual(len(options), 2)
        self.assertTrue(all(
            option['value'].startswith('Telnyx.') for option in options))

    def test_changing_voice_filters_clears_an_incompatible_voice(self):
        settings = self.env['connect.settings'].sudo().new({
            'telnyx_system_voice_language': 'en-US',
            'telnyx_system_voice_provider': 'aws',
            'telnyx_system_voice': 'Polly.Joanna',
        })

        settings.telnyx_system_voice_provider = 'basic'
        settings._onchange_telnyx_system_voice_filters()

        self.assertFalse(settings.telnyx_system_voice)

    def test_voice_catalog_refresh_reopens_settings_in_new_web_load(self):
        with patch.object(
                Settings, '_sync_telnyx_tts_voices', autospec=True):
            action = self.env['connect.settings'].telnyx_sync_tts_voices()

        settings_action = self.env.ref(
            'connect_telnyx.telnyx_settings_action')
        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertEqual(action['target'], 'self')
        self.assertIn('/web?telnyx_voices=', action['url'])
        self.assertIn('#action={}'.format(settings_action.id), action['url'])

    def test_texml_app_applies_system_voice_to_custom_markup(self):
        self.env['connect.settings'].sudo().set_param(
            'telnyx_system_voice', 'woman')
        app = self.env['connect.telnyx.texml'].with_context(
            install_mode=True).create({
                'name': 'System Voice Test',
                'code_type': 'texml',
                'texml': '<Response><Say>Hello</Say></Response>',
            })

        self.assertIn('<Say voice="woman">Hello</Say>', app.render())

    def test_user_and_callflow_use_system_voice_as_fallback(self):
        self.env['connect.settings'].sudo().set_param(
            'telnyx_system_voice', 'woman')
        user = self._create_connect_user(
            'tx_system_voice', greeting_message='Welcome')
        user_response = VoiceResponse()
        user.get_telnyx_greeting_message(user_response)

        callflow = self.env['connect.telnyx.callflow'].create({
            'name': 'System Voice Flow',
            'prompt_message': 'Choose an option',
            'voice': False,
        })
        flow_response = VoiceResponse()
        callflow.get_prompt_message(flow_response)

        self.assertIn('voice="woman"', str(user_response))
        self.assertIn('voice="woman"', str(flow_response))
