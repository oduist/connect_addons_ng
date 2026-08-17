# -*- coding: utf-8 -*-
import base64
from unittest.mock import MagicMock, patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.connect.models.settings import Settings as CoreSettings
from odoo.addons.connect_telnyx.models.settings import Settings

from .common import TelnyxTestCommon


@tagged('at_install', '-post_install')
class TestTelnyxAIAssistant(TelnyxTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param(
            'connect.api_url', 'https://odoo.example.test/')
        cls.env['connect.settings'].sudo().set_param(
            'telnyx_api_key', 'test-api-key')
        cls.env['connect.settings'].sudo().set_param(
            'telnyx_ai_summary_insight_id', 'insight-test')
        cls.env['connect.settings'].sudo().set_param(
            'telnyx_ai_summary_group_id', 'group-test')
        cls.Assistant = cls.env['connect.telnyx.ai_assistant'].with_context(
            skip_telnyx_ai_sync=True)
        cls.assistant = cls.Assistant.create({
            'name': 'Support Agent',
            'instructions': 'Help the caller.',
            'sid': 'assistant-test',
        })

    def test_remote_payload_has_safe_defaults_and_tools(self):
        payload = self.assistant._remote_payload()
        self.assertEqual(payload['enabled_features'], ['telephony'])
        self.assertEqual(payload['tools'][0], {
            'type': 'hangup', 'hangup': {}})
        self.assertFalse(
            payload['telephony_settings']['recording_settings']['enabled'])
        tool_names = [
            item.get('webhook', {}).get('name') for item in payload['tools']
        ]
        self.assertIn('lookup_contact', tool_names)
        self.assertIn('add_contact_note', tool_names)
        self.assertIn('register_call_request', tool_names)
        self.assertNotIn('upsert_crm_lead', tool_names)
        webhook = next(
            item['webhook'] for item in payload['tools']
            if item.get('webhook', {}).get('name') == 'lookup_contact')
        self.assertEqual(
            webhook['headers'][0]['value'], self.assistant.tool_token)
        self.assertIn('Odoo receptionist policy', payload['instructions'])
        self.assertIn('register a request', payload['instructions'])
        self.assertIn(
            'If a transfer does not connect', payload['instructions'])
        self.assertIn('How to speak', payload['instructions'])
        self.assertIn(
            'at most two short sentences', payload['instructions'])
        self.assertIn(
            'Never repeat a sentence you already said',
            payload['instructions'])
        for variable in (
            'conversation_language_name',
            'conversation_language',
            'conversation_language_source',
            'language_switch_allowed',
        ):
            self.assertIn('{{%s}}' % variable, payload['instructions'])
        self.assertEqual(payload['greeting'], '{{odoo_initial_greeting}}')
        self.assertEqual(
            payload['dynamic_variables']['conversation_language'], 'en-US')
        self.assertTrue(
            payload['dynamic_variables']['odoo_initial_greeting'])
        self.assertEqual(payload['transcription'], {
            'model': 'deepgram/nova-3',
            'language': 'auto',
        })
        self.assertEqual(payload['voice_settings'], {
            'voice': self.assistant.voice,
            'voice_speed': 1.0,
            'expressive_mode': False,
        })
        self.assertEqual(payload['dynamic_variables_webhook_timeout_ms'], 5000)

    def test_remote_payload_publishes_voice_controls(self):
        self.assistant.with_context(skip_telnyx_ai_sync=True).write({
            'voice': 'Telnyx.Ultra.callie',
            'language_boost': 'auto',
            'expressive_mode': True,
        })

        self.assertEqual(self.assistant._remote_payload()['voice_settings'], {
            'voice': 'Telnyx.Ultra.callie',
            'voice_speed': 1.0,
            'language_boost': 'auto',
            'expressive_mode': True,
        })

    def test_remote_values_read_voice_controls(self):
        values = self.Assistant._remote_values({
            'id': 'assistant-remote',
            'name': 'Remote Agent',
            'instructions': 'Help.',
            'voice_settings': {
                'voice': 'Telnyx.Ultra.callie',
                'voice_speed': 0.9,
                'language_boost': 'Polish',
                'expressive_mode': True,
            },
        }, imported=True)

        self.assertEqual(values['language_boost'], 'Polish')
        self.assertTrue(values['expressive_mode'])
        self.assertEqual(values['voice_speed'], 0.9)

    def test_voice_speed_outside_supported_range_is_rejected(self):
        for speed in (2.0, 0.25):
            with self.assertRaises(ValidationError):
                self.assistant.with_context(skip_telnyx_ai_sync=True).write(
                    {'voice_speed': speed})

        for speed in (0.5, 1.5):
            self.assistant.with_context(skip_telnyx_ai_sync=True).write(
                {'voice_speed': speed})
            self.assertEqual(self.assistant.voice_speed, speed)

    def test_remote_voice_speed_is_clamped(self):
        values = self.Assistant._remote_values({
            'id': 'assistant-remote',
            'name': 'Remote Agent',
            'instructions': 'Help.',
            'voice_settings': {
                'voice': 'Telnyx.Ultra.callie',
                'voice_speed': 2.0,
            },
        })

        self.assertEqual(values['voice_speed'], 1.5)

    def test_unique_contact_supplies_language_and_localized_greeting(self):
        partner = self.env['res.partner'].create({
            'name': 'Language Caller',
            'phone': '+15550007777',
            'lang': 'en_US',
        })
        values = self.assistant._partner_values(partner, match_count=1)
        self.assertEqual(values['customer_language'], 'en_US')
        self.assertEqual(values['conversation_language'], 'en-US')
        self.assertEqual(values['conversation_language_code'], 'en')
        self.assertEqual(values['conversation_language_source'], 'contact')
        self.assertTrue(values['language_switch_allowed'])
        self.assertIn(partner.display_name, values['odoo_initial_greeting'])
        self.assertIn('Am I speaking with', values['odoo_initial_greeting'])

    def test_fixed_language_ignores_contact_language_switching(self):
        partner = self.env['res.partner'].create({
            'name': 'Fixed Language Caller',
            'phone': '+15550007778',
            'lang': 'en_US',
        })
        self.assistant.with_context(skip_telnyx_ai_sync=True).language_mode = (
            'fixed')
        values = self.assistant._partner_values(partner, match_count=1)
        self.assertEqual(values['conversation_language_source'], 'agent')
        self.assertFalse(values['language_switch_allowed'])

    def test_automatic_language_uses_agent_greeting_as_fallback(self):
        self.assistant.with_context(skip_telnyx_ai_sync=True).language_mode = (
            'automatic')
        values = self.assistant._partner_values(
            self.env['res.partner'], match_count=0)
        self.assertEqual(values['conversation_language_source'], 'automatic')
        self.assertTrue(values['language_switch_allowed'])
        self.assertEqual(values['odoo_initial_greeting'], self.assistant.greeting)

    def test_imported_assistant_payload_omits_the_hangup_tool(self):
        """Telnyx keeps the hangup tool an imported assistant already has
        and rejects a second one."""
        imported = self.Assistant.create({
            'name': 'Imported Agent',
            'instructions': 'Imported.',
            'sid': 'assistant-imported',
            'imported': True,
        })
        tool_types = [item['type'] for item in imported._remote_payload()['tools']]
        self.assertNotIn('hangup', tool_types)
        self.assertIn('webhook', tool_types)

    def test_push_retries_with_a_known_voice_when_telnyx_rejects_it(self):
        from odoo.addons.connect_telnyx.models.ai_assistant import DEFAULT_VOICE
        self.assistant.with_context(skip_telnyx_ai_sync=True).write(
            {
                'voice': 'Telnyx.Ultra.deleted-voice',
                'language_boost': 'auto',
                'expressive_mode': True,
            })
        voices = []

        def api_response(_settings, method, path, **kwargs):
            payload = kwargs.get('payload') or {}
            voice = (payload.get('voice_settings') or {}).get('voice')
            voices.append(voice)
            if voice != DEFAULT_VOICE:
                raise ValidationError(
                    'Telnyx API returned HTTP 400: Voice `{}` not found. '
                    'Ensure the voice ID is valid.'.format(voice))
            return {'data': {'id': self.assistant.sid, 'name': 'Support Agent',
                             'instructions': 'Help the caller.'}}

        with patch.object(Settings, 'telnyx_api_request', autospec=True,
                          side_effect=api_response), patch.object(
                              CoreSettings, 'connect_notify', autospec=True):
            self.assistant._update_remote()
        self.assertEqual(
            voices, ['Telnyx.Ultra.deleted-voice', DEFAULT_VOICE])
        self.assertEqual(self.assistant.voice, DEFAULT_VOICE)
        self.assertFalse(self.assistant.language_boost)
        self.assertFalse(self.assistant.expressive_mode)

    def test_number_renders_ai_assistant_texml(self):
        number = self.env['connect.telnyx.number'].create({
            'phone_number': '+15550001111',
            'sid': 'number-test',
            'destination': 'ai_assistant',
            'ai_assistant': self.assistant.id,
        })
        xml = number.render()
        self.assertIn('<Connect>', xml)
        self.assertIn('<AIAssistant id="assistant-test"', xml)

    def test_extension_renders_ai_assistant_texml(self):
        extension = self.env['connect.telnyx.exten'].create({
            'number': '710',
            'dst': 'connect.telnyx.ai_assistant,{}'.format(self.assistant.id),
        })
        self.assertEqual(self.assistant.exten, extension)
        xml = extension.render(request={'To': 'sip:710@test.sip.telnyx.com'})
        self.assertIn('<AIAssistant id="assistant-test"', xml)

    def test_domain_routes_internal_sip_call_to_assistant_extension(self):
        self.env['connect.telnyx.exten'].create({
            'number': '711',
            'dst': 'connect.telnyx.ai_assistant,{}'.format(self.assistant.id),
        })
        request = {
            'To': 'sip:711@{}'.format(self.domain.domain_name),
            'From': 'sip:caller@sip.telnyx.com',
            'CallSid': 'assistant-extension-call',
            'CallStatus': 'initiated',
        }
        with patch.object(
                type(self.env['connect.call']), 'on_telnyx_call_status',
                autospec=True):
            xml = self.domain.route_call(request)
        self.assertIn('<AIAssistant id="assistant-test"', xml)

    def test_turn_taking_settings_are_published(self):
        payload = self.assistant._remote_payload()
        interruption = payload['interruption_settings']
        self.assertTrue(interruption['enable'])
        self.assertFalse(interruption['disable_greeting_interruption'])
        speaking = interruption['start_speaking_plan']
        self.assertEqual(speaking['wait_seconds'], 0.4)
        self.assertEqual(speaking['transcription_endpointing_plan'], {
            'on_punctuation_seconds': 0.3,
            'on_no_punctuation_seconds': 1.0,
            'on_number_seconds': 0.6,
        })

        with self.assertRaises(ValidationError):
            self.assistant.with_context(skip_telnyx_ai_sync=True).write(
                {'endpointing_no_punctuation_secs': -1})

    def test_remote_values_read_turn_taking_settings(self):
        values = self.Assistant._remote_values({
            'id': 'assistant-remote',
            'name': 'Remote Agent',
            'instructions': 'Help.',
            'interruption_settings': {
                'enable': False,
                'disable_greeting_interruption': True,
                'start_speaking_plan': {
                    'wait_seconds': 0.1,
                    'transcription_endpointing_plan': {
                        'on_punctuation_seconds': 0.1,
                        'on_no_punctuation_seconds': 0.1,
                        'on_number_seconds': 0.1,
                    },
                },
            },
        })

        self.assertFalse(values['allow_interruptions'])
        self.assertTrue(values['protect_greeting'])
        self.assertEqual(values['start_speaking_wait_secs'], 0.1)
        self.assertEqual(values['endpointing_no_punctuation_secs'], 0.1)

    def test_caller_silence_timeout_is_published(self):
        payload = self.assistant._remote_payload()
        self.assertEqual(
            payload['telephony_settings']['user_idle_timeout_secs'], 60)

        self.assistant.with_context(skip_telnyx_ai_sync=True).write(
            {'user_idle_timeout_secs': 0})
        payload = self.assistant._remote_payload()
        self.assertIsNone(
            payload['telephony_settings']['user_idle_timeout_secs'])

        with self.assertRaises(ValidationError):
            self.assistant.with_context(skip_telnyx_ai_sync=True).write(
                {'user_idle_timeout_secs': 5})

    def _conversation_ended_params(self, reason):
        return {
            'CallSid': 'v3:ai-conversation-call',
            'From': '+15550008888',
            'To': '+15550009999',
            'CallStatus': 'conversation_ended',
            'Reason': reason,
            'ConversationId': 'conversation-test',
            'DurationSec': '1',
            'TtsProvider': 'telnyx',
            'TtsModelId': 'Ultra',
            'TtsVoiceId': 'voice-test',
        }

    def test_failed_ai_conversation_marks_the_call_with_an_error(self):
        call = self.env['connect.call'].create({
            'caller': '+15550008888',
            'called': '+15550009999',
            'direction': 'incoming',
            'status': 'answered',
        })
        channel = self.env['connect.channel'].create({
            'sid': 'v3:ai-conversation-call',
            'call': call.id,
            'status': 'answered',
        })

        with patch.object(
                type(self.env['connect.channel']), 'process_channel_event',
                autospec=True, return_value=channel):
            self.env['connect.call'].on_telnyx_call_status(
                self._conversation_ended_params('greeting_error'))

        self.assertTrue(call.has_error)
        self.assertEqual(call.error_code, 'greeting_error')
        self.assertIn('greeting audio', call.error_message)
        self.assertIn('telnyx Ultra voice-test', call.error_message)
        self.assertEqual(call.telnyx_ai_conversation_id, 'conversation-test')

    def test_normal_ai_conversation_end_is_not_an_error(self):
        call = self.env['connect.call'].create({
            'caller': '+15550008888',
            'called': '+15550009999',
            'direction': 'incoming',
            'status': 'answered',
        })
        channel = self.env['connect.channel'].create({
            'sid': 'v3:ai-conversation-call',
            'call': call.id,
            'status': 'answered',
        })

        with patch.object(
                type(self.env['connect.channel']), 'process_channel_event',
                autospec=True, return_value=channel):
            self.env['connect.call'].on_telnyx_call_status(
                self._conversation_ended_params('user_hangup'))

        self.assertFalse(call.has_error)
        self.assertFalse(call.error_code)

    def test_unknown_ai_failure_reason_is_reported_verbatim(self):
        error = self.env['connect.call']._telnyx_ai_conversation_error(
            self._conversation_ended_params('llm_failure'))

        self.assertEqual(error['error_code'], 'llm_failure')
        self.assertIn('llm_failure', error['error_message'])

    def test_sync_pushes_local_assistants_without_remote_import(self):
        assistant_model = type(self.env['connect.telnyx.ai_assistant'])
        with patch.object(
                assistant_model, '_update_remote', autospec=True,
                return_value=True) as update_mock, patch.object(
                    Settings, 'telnyx_api_request', autospec=True
                ) as request_mock:
            self.env['connect.telnyx.ai_assistant'].sync()
        self.assertTrue(update_mock.called)
        request_mock.assert_not_called()

    def test_summary_instructions_edit_recreates_insight(self):
        settings = self.env['connect.settings'].sudo()
        settings.set_param('telnyx_ai_summary_insight_id', 'insight-old')
        settings.set_param('telnyx_ai_summary_group_id', 'group-test')
        calls = []

        def api_response(_settings, method, path, **kwargs):
            calls.append((method, path, kwargs.get('payload')))
            if method == 'POST' and path == 'ai/conversations/insights':
                return {'data': {'id': 'insight-new'}}
            return {}

        with patch.object(
                Settings, 'telnyx_api_request', autospec=True,
                side_effect=api_response):
            settings.set_param(
                'telnyx_ai_summary_instructions', 'Summarize in Polish.')

        self.assertIn(
            ('DELETE', 'ai/conversations/insights/insight-old', None), calls)
        create_call = next(
            call for call in calls
            if call[0] == 'POST' and call[1] == 'ai/conversations/insights')
        self.assertEqual(
            create_call[2]['instructions'], 'Summarize in Polish.')
        self.assertIn(
            ('POST',
             'ai/conversations/insight-groups/group-test/insights/'
             'insight-new/assign',
             None),
            calls)
        # The group is reused, only the insight is rebuilt.
        self.assertFalse([
            call for call in calls
            if call[1] == 'ai/conversations/insight-groups'])
        self.assertEqual(
            settings.get_param('telnyx_ai_summary_insight_id'), 'insight-new')

    def test_summary_instructions_edit_without_insight_skips_api(self):
        settings = self.env['connect.settings'].sudo()
        settings.set_param('telnyx_ai_summary_insight_id', False)

        with patch.object(
                Settings, 'telnyx_api_request', autospec=True
        ) as request_mock:
            settings.set_param(
                'telnyx_ai_summary_instructions', 'Summarize in German.')

        request_mock.assert_not_called()
        self.assertEqual(
            settings.get_param('telnyx_ai_summary_instructions'),
            'Summarize in German.')

    def test_ensure_summary_group_uses_configured_instructions(self):
        settings = self.env['connect.settings'].sudo()
        settings.set_param('telnyx_ai_summary_insight_id', False)
        settings.set_param('telnyx_ai_summary_group_id', 'group-test')
        # No insight is published, so this write does not call Telnyx.
        settings.set_param(
            'telnyx_ai_summary_instructions', 'Report the agreed next step.')
        payloads = []

        def api_response(_settings, method, path, **kwargs):
            payloads.append((method, path, kwargs.get('payload')))
            if method == 'POST' and path == 'ai/conversations/insights':
                return {'data': {'id': 'insight-fresh'}}
            return {}

        with patch.object(
                Settings, 'telnyx_api_request', autospec=True,
                side_effect=api_response):
            group_id = self.env[
                'connect.telnyx.ai_assistant']._ensure_summary_group()

        self.assertEqual(group_id, 'group-test')
        create_call = next(
            call for call in payloads
            if call[0] == 'POST' and call[1] == 'ai/conversations/insights')
        self.assertEqual(
            create_call[2]['instructions'], 'Report the agreed next step.')

    def test_sync_push_failure_notification_is_sticky(self):
        settings = self.env['connect.settings'].sudo()
        settings.set_param('telnyx_ai_summary_insight_id', 'insight-test')
        settings.set_param('telnyx_ai_summary_group_id', 'group-test')
        assistant_model = type(self.env['connect.telnyx.ai_assistant'])
        settings_model = type(self.env['connect.settings'])
        with patch.object(
                    assistant_model, '_update_remote', autospec=True,
                    side_effect=RuntimeError('Unsupported model')), patch.object(
                        settings_model, 'connect_notify', autospec=True
                    ) as notify_mock:
            self.env['connect.telnyx.ai_assistant'].sync()

        warning_call = next(
            call for call in notify_mock.call_args_list
            if call.kwargs.get('title') == 'AI Assistant Sync Warning'
        )
        self.assertTrue(warning_call.kwargs.get('sticky'))

    def test_create_respects_auto_sync_disabled(self):
        settings = self.env['connect.settings'].sudo()
        original = settings.get_param('telnyx_auto_sync')
        settings.set_param('telnyx_auto_sync', False)
        try:
            with patch.object(
                    Settings, 'telnyx_api_request', autospec=True
            ) as request_mock:
                assistant = self.env['connect.telnyx.ai_assistant'].create({
                    'name': 'Local Draft Agent',
                    'instructions': 'Stay local.',
                })
        finally:
            settings.set_param('telnyx_auto_sync', original)
        self.assertFalse(assistant.sid)
        request_mock.assert_not_called()

    def test_ai_call_wizard_uses_texml_connection_endpoint(self):
        # The wizard dials through the number application, whatever
        # applications the database already contains.
        number_app = self.env['connect.telnyx.number'].get_number_app()
        number_app.with_context(skip_telnyx_sync=True).write(
            {'sid': 'texml-connection-test'})
        caller_id = self.env['connect.telnyx.outgoing_callerid'].create({
            'number': '+15550009999',
            'friendly_name': 'Test caller',
        })
        partner = self.env['res.partner'].create({
            'name': 'AI Callee', 'phone': '+15550008888'})
        wizard = self.env['connect.telnyx.ai_call_wizard'].create({
            'assistant': self.assistant.id,
            'caller_id': caller_id.id,
            'to_number': '15550008888',
            'partner': partner.id,
        })

        def api_response(_settings, method, path, **kwargs):
            self.assertEqual(method, 'POST')
            self.assertEqual(path, 'texml/ai_calls/texml-connection-test')
            self.assertEqual(kwargs['payload']['To'], '+15550008888')
            self.assertEqual(
                kwargs['payload']['AIAssistantId'], self.assistant.sid)
            variables = kwargs['payload']['AIAssistantDynamicVariables']
            self.assertEqual(variables['customer_name'], partner.display_name)
            self.assertEqual(variables['conversation_language'], 'en-US')
            self.assertIn(partner.display_name,
                          variables['odoo_initial_greeting'])
            return {'call_sid': 'v3:test-ai-call'}

        with patch.object(
                Settings, 'telnyx_api_request', autospec=True,
                side_effect=api_response):
            wizard.action_call()
        channel = self.env['connect.channel'].search([
            ('sid', '=', 'v3:test-ai-call')])
        self.assertEqual(len(channel), 1)
        self.assertEqual(channel.called, '+15550008888')

    def test_contact_tool_is_allowlisted(self):
        partner = self.env['res.partner'].create({
            'name': 'AI Caller', 'phone': '+15550002222'})
        result = self.assistant.execute_tool(
            'lookup_contact', {'phone': '+15550002222'})
        self.assertTrue(result['found'])
        self.assertEqual(result['partner_id'], partner.id)
        result = self.assistant.execute_tool(
            'add_contact_note', {
                'phone': '+15550002222', 'note': 'Requested a callback.'})
        self.assertTrue(result['ok'])
        self.assertTrue(partner.message_ids)

    def test_agent_can_register_a_qualified_call_request(self):
        call = self.env['connect.call'].create({
            'caller': '+15550005555',
            'called': '+15550001111',
            'status': 'in-progress',
            'direction': 'incoming',
        })
        self.env['connect.channel'].create({
            'sid': 'v3:request-call',
            'call': call.id,
            'caller': '+15550005555',
            'called': '+15550001111',
            'status': 'in-progress',
            'technical_direction': 'inbound',
        })
        result = self.assistant.execute_tool(
            'register_call_request', {
                'title': 'Pricing request',
                'summary': 'Caller needs a quote for ten seats.',
                'requested_action': 'Sales should call back tomorrow.',
            }, call_control_id='v3:request-call')
        self.assertTrue(result['ok'])
        self.assertEqual(result['call_id'], call.id)
        self.assertTrue(call.message_ids.filtered(
            lambda message: 'Pricing request' in (message.body or '')))

    def test_contact_lookup_rejects_duplicate_phone_numbers(self):
        self.env['res.partner'].create({
            'name': 'First Caller', 'phone': '+15550006666'})
        self.env['res.partner'].create({
            'name': 'Second Caller', 'mobile': '+15550006666'})
        partner, match_count = self.assistant._strict_partner_match(
            '+15550006666')
        self.assertFalse(partner)
        self.assertEqual(match_count, 2)
        result = self.assistant.execute_tool(
            'lookup_contact', {'phone': '+15550006666'})
        self.assertFalse(result['found'])
        self.assertTrue(result['ambiguous'])
        self.assertEqual(result['match_count'], 2)

    def test_personal_transfer_uses_registered_web_phone(self):
        manager = self._create_web_phone_user('ai_manager')
        self.assistant.with_context(skip_telnyx_ai_sync=True).write({
            'manager': manager.id,
            'receptionist_mode': 'personal',
        })
        user_model = type(self.env['connect.user'])
        with patch.object(
                user_model, '_telnyx_registration_status', autospec=True,
                return_value={
                    'registered': True,
                    'sip_registration_status': 'registered',
                }):
            targets, unavailable = self.assistant._transfer_targets()
        self.assertEqual(unavailable, [])
        self.assertEqual(targets, [{
            'name': manager.name,
            'to': 'sip:{}@sip.telnyx.com'.format(
                manager.telnyx_client_username),
        }])

    def test_offline_manager_is_not_a_transfer_target(self):
        manager = self._create_web_phone_user('ai_offline_manager')
        self.assistant.with_context(skip_telnyx_ai_sync=True).manager = manager
        user_model = type(self.env['connect.user'])
        with patch.object(
                user_model, '_telnyx_registration_status', autospec=True,
                return_value={
                    'registered': False,
                    'sip_registration_status': 'failed',
                }):
            targets, unavailable = self.assistant._transfer_targets()
        self.assertEqual(targets, [])
        self.assertEqual(unavailable, [manager.name])

    def test_company_receptionist_labels_department_targets(self):
        seller = self._create_web_phone_user('ai_sales_user')
        callflow = self.env['connect.telnyx.callflow'].create({
            'name': 'Sales',
            'ring_users': [(6, 0, seller.ids)],
        })
        self.assistant.with_context(skip_telnyx_ai_sync=True).write({
            'receptionist_mode': 'company',
            'transfer_callflows': [(6, 0, callflow.ids)],
            'check_registration_before_transfer': False,
        })
        targets, unavailable = self.assistant._transfer_targets()
        self.assertEqual(unavailable, [])
        self.assertEqual(targets, [{
            'name': 'Sales',
            'to': 'sip:{}@sip.telnyx.com'.format(
                seller.telnyx_client_username),
        }])

    def test_registration_api_error_keeps_advisory_fallback(self):
        manager = self._create_web_phone_user('ai_unknown_manager')
        user_model = type(self.env['connect.user'])
        with patch.object(
                user_model, '_telnyx_registration_status', autospec=True,
                side_effect=ValidationError('status unavailable')):
            target = manager._telnyx_transfer_target()
        self.assertEqual(target['registration'], 'unknown')
        self.assertEqual(
            target['to'], 'sip:{}@sip.telnyx.com'.format(
                manager.telnyx_client_username))

    def test_transfer_tool_is_managed_and_attached_to_assistant(self):
        manager = self._create_web_phone_user('ai_tool_manager')
        self.assistant.with_context(skip_telnyx_ai_sync=True).manager = manager
        calls = []

        def api_response(_settings, method, path, **kwargs):
            calls.append((method, path, kwargs.get('payload')))
            if (method, path) == ('POST', 'ai/tools'):
                return {'id': 'tool-transfer-test'}
            return {'data': {
                'id': self.assistant.sid,
                'version_id': 'version-test',
            }}

        with patch.object(
                Settings, 'telnyx_api_request', autospec=True,
                side_effect=api_response):
            self.assistant._update_remote()
        tool_payload = next(
            payload for method, path, payload in calls
            if (method, path) == ('POST', 'ai/tools'))
        self.assertEqual(
            tool_payload['transfer']['targets'], '{{transfer_targets}}')
        self.assertEqual(
            tool_payload['transfer']['from'], '{{telnyx_agent_target}}')
        self.assertIn(
            'confirmed identity',
            tool_payload['transfer']['warm_transfer_instructions'])
        self.assertEqual(
            tool_payload['transfer']['warm_message_delay_ms'], 2000)
        assistant_payload = next(
            payload for method, path, payload in calls
            if path == 'ai/assistants/assistant-test')
        self.assertEqual(assistant_payload['tool_ids'], ['tool-transfer-test'])

    def test_zero_warm_transfer_delay_restores_immediate_playback(self):
        self.assistant.with_context(skip_telnyx_ai_sync=True).write({
            'warm_transfer_message_delay_ms': 0,
        })
        payload = self.assistant._transfer_tool_payload()
        self.assertIsNone(payload['transfer']['warm_message_delay_ms'])

    def test_conversation_sync_is_idempotent(self):
        call = self.env['connect.call'].create({
            'caller': '+15550003333',
            'called': '+15550004444',
            'status': 'completed',
            'direction': 'incoming',
        })
        self.env['connect.channel'].create({
            'sid': 'v3:test-call',
            'call': call.id,
            'caller': '+15550003333',
            'called': '+15550004444',
            'status': 'completed',
            'technical_direction': 'inbound',
        })
        conversation = {
            'id': 'conversation-test',
            'metadata': {
                'assistant_id': self.assistant.sid,
                'call_control_id': 'v3:test-call',
                'telnyx_conversation_channel': 'phone_call',
            },
        }

        def api_response(_settings, _method, path, **kwargs):
            if path.endswith('/messages'):
                return {'data': [
                    {'role': 'user', 'text': 'I need help.'},
                    {'role': 'assistant', 'text': 'I can help.'},
                ]}
            return {'data': [{
                'status': 'completed',
                'conversation_insights': [{'result': 'Issue resolved.'}],
            }]}

        with patch.object(
                Settings, 'telnyx_api_request', autospec=True,
                side_effect=api_response):
            self.env['connect.call'].telnyx_sync_ai_conversation(conversation)
            self.env['connect.call'].telnyx_sync_ai_conversation(conversation)
        recordings = self.env['connect.recording'].search([
            ('sid', '=', 'conversation-test'), ('source', '=', 'telnyx-ai')])
        self.assertEqual(len(recordings), 1)
        self.assertIn('USER: I need help.', recordings.transcript)
        self.assertEqual(call.telnyx_ai_conversation_id, 'conversation-test')

    def test_insight_webhook_resolves_conversation_from_call_control_id(self):
        call = self.env['connect.call'].create({
            'caller': '+15550005555',
            'called': '+15550006666',
            'status': 'completed',
            'direction': 'incoming',
            'telnyx_ai_conversation_id': 'conversation-event',
        })
        self.env['connect.channel'].create({
            'sid': 'v3:event-call',
            'call': call.id,
            'caller': call.caller,
            'called': call.called,
            'status': 'completed',
            'technical_direction': 'inbound',
        })

        def api_response(_settings, _method, path, **kwargs):
            if path == 'ai/conversations/conversation-event':
                return {'data': {
                    'id': 'conversation-event',
                    'metadata': {
                        'assistant_id': self.assistant.sid,
                        'call_control_id': 'v3:event-call',
                    },
                }}
            if path.endswith('/messages'):
                return {'data': [
                    {'role': 'user', 'text': 'Please help me.'},
                ]}
            if path == 'recordings':
                return {'data': []}
            self.fail('Unexpected Telnyx API path: {}'.format(path))

        event = {
            'data': {
                'record_type': 'event',
                'event_type': 'call.conversation_insights.generated',
                'payload': {
                    'call_control_id': 'v3:event-call',
                    'results': [{'result': 'The caller requested help.'}],
                },
            },
        }
        with patch.object(
                Settings, 'telnyx_api_request', autospec=True,
                side_effect=api_response):
            recording = self.env[
                'connect.call'
            ].telnyx_apply_ai_insights(event)

        self.assertTrue(recording)
        self.assertEqual(recording.call, call)
        self.assertIn('USER: Please help me.', recording.transcript)
        self.assertIn('The caller requested help.', recording.summary)
        self.assertFalse(recording.transcription_pending)

    def test_telnyx_ai_audio_is_attached_without_openai_transcription(self):
        self.env['connect.settings'].sudo().set_param(
            'transcript_calls', True)
        call = self.env['connect.call'].create({
            'caller': '+15550007777',
            'called': '+15550008888',
            'status': 'completed',
            'direction': 'incoming',
        })
        self.env['connect.channel'].create({
            'sid': 'v3:audio-call',
            'call': call.id,
            'caller': call.caller,
            'called': call.called,
            'status': 'completed',
            'technical_direction': 'inbound',
        })
        conversation = {
            'id': 'conversation-audio',
            'metadata': {
                'assistant_id': self.assistant.sid,
                'call_control_id': 'v3:audio-call',
                'telnyx_conversation_channel': 'phone_call',
            },
        }

        def api_response(_settings, _method, path, **kwargs):
            if path.endswith('/messages'):
                return {'data': [
                    {'role': 'user', 'text': 'Audio test.'},
                    {'role': 'assistant', 'text': 'Understood.'},
                ]}
            if path.endswith('/conversations-insights'):
                return {'data': [{
                    'status': 'completed',
                    'conversation_insights': [
                        {'result': 'Audio test completed.'},
                    ],
                }]}
            if path == 'recordings':
                self.assertEqual(
                    kwargs['params']['filter[call_control_id]'],
                    'v3:audio-call',
                )
                return {'data': [{
                    'id': 'recording-audio',
                    'call_control_id': 'v3:audio-call',
                    'status': 'completed',
                    'duration_millis': 4200,
                    'download_urls': {
                        'mp3': 'https://example.test/audio.mp3',
                    },
                }]}
            self.fail('Unexpected Telnyx API path: {}'.format(path))

        download = MagicMock()
        download.headers = {'Content-Length': '5'}
        download.iter_content.return_value = [b'AUDIO']
        with patch.object(
                Settings, 'telnyx_api_request', autospec=True,
                side_effect=api_response), patch(
                    'odoo.addons.connect_telnyx.models.recording.requests.get',
                    return_value=download,
                ) as get_audio:
            recording = self.env[
                'connect.call'
            ].telnyx_sync_ai_conversation(conversation)
            self.env['connect.call'].telnyx_sync_ai_conversation(conversation)

        get_audio.assert_called_once_with(
            'https://example.test/audio.mp3', stream=True, timeout=30)
        download.raise_for_status.assert_called_once_with()
        self.assertEqual(recording.telnyx_recording_id, 'recording-audio')
        self.assertEqual(recording.recording_filename, 'recording-audio.mp3')
        self.assertEqual(
            base64.b64decode(recording.recording_attachment), b'AUDIO')
        self.assertEqual(recording.duration, 4)
        self.assertFalse(recording.media_url)
        self.assertFalse(recording.transcription_pending)
        self.assertFalse(recording.transcription_error)
