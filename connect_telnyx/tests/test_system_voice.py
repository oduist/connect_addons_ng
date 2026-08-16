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
        options = dict(
            self.env['connect.settings']._get_telnyx_voice_selection())
        self.assertIn('Telnyx.NaturalHD.astra', options)
        self.assertIn('AWS.Polly.Marlene-Neural', options)

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
