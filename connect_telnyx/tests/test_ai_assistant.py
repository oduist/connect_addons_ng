# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from odoo.addons.connect_telnyx.models.settings import Settings


@tagged('at_install', '-post_install')
class TestTelnyxAIAssistant(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param(
            'connect.api_url', 'https://odoo.example.test/')
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
        self.assertFalse(
            payload['telephony_settings']['recording_settings']['enabled'])
        tool_names = [
            item.get('webhook', {}).get('name') for item in payload['tools']
        ]
        self.assertIn('lookup_contact', tool_names)
        self.assertIn('add_contact_note', tool_names)
        self.assertNotIn('upsert_crm_lead', tool_names)
        webhook = next(
            item['webhook'] for item in payload['tools']
            if item.get('webhook', {}).get('name') == 'lookup_contact')
        self.assertEqual(
            webhook['headers'][0]['value'], self.assistant.tool_token)

    def test_number_renders_ai_assistant_texml(self):
        number = self.env['connect.telnyx.number'].create({
            'phone_number': '+15550001111',
            'sid': 'number-test',
        })
        number.with_context(skip_telnyx_sync=True).write({
            'destination': 'ai_assistant',
            'ai_assistant': self.assistant.id,
        })
        xml = number.render()
        self.assertIn('<Connect>', xml)
        self.assertIn('<AIAssistant id="assistant-test"', xml)

    def test_sync_imports_remote_assistant_idempotently(self):
        settings = self.env['connect.settings'].sudo()
        settings.set_param('telnyx_ai_summary_insight_id', 'insight-test')
        settings.set_param('telnyx_ai_summary_group_id', 'group-test')
        remote_item = {
                'id': 'assistant-imported',
                'name': 'Imported Agent',
                'instructions': 'Imported instructions.',
                'greeting': 'Hello',
                'telephony_settings': {
                    'time_limit_secs': 600,
                    'recording_settings': {'enabled': True},
                },
            }

        def api_response(_settings, method, path, **kwargs):
            if method == 'GET' and path == 'ai/assistants':
                return {'data': [remote_item]}
            return remote_item

        with patch.object(
                Settings, 'telnyx_api_request', autospec=True,
                side_effect=api_response):
            self.env['connect.telnyx.ai_assistant'].sync()
            self.env['connect.telnyx.ai_assistant'].sync()
        records = self.env['connect.telnyx.ai_assistant'].search([
            ('sid', '=', 'assistant-imported')])
        self.assertEqual(len(records), 1)
        self.assertTrue(records.imported)
        self.assertTrue(records.record_calls)

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
