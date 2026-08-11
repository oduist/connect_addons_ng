# -*- coding: utf-8 -*-
import json
from unittest import mock

from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged
from odoo.tests.common import HttpCase, TransactionCase


@tagged('post_install', '-at_install', 'connect_pipecat')
class TestPipecatAgent(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.settings = cls.env['connect.settings'].sudo()
        cls.settings.set_param('pipecat_sidecar_url', 'wss://voice.example.com')
        cls.agent = cls.env['connect.pipecat.agent'].create({
            'name': 'Reception',
            'system_prompt': 'Help the caller.',
            'record_calls': False,
        })

    def test_generate_dialplan(self):
        exten = self.env['connect.freeswitch.exten'].create({
            'number': '9100',
            'model': 'connect.pipecat.agent',
            'res_id': self.agent.id,
        })
        xml = self.agent.generate_dialplan({}, exten=exten)
        self.assertIn('uuid_audio_fork(', xml)
        self.assertIn('wss://voice.example.com/ws?call_uuid=', xml)
        self.assertIn('agent_id=%s' % self.agent.id, xml)
        self.assertIn('MOD_AUDIO_BASIC_AUTH_USERNAME=pipecat', xml)
        self.assertIn('MOD_AUDIO_BASIC_AUTH_PASSWORD=', xml)
        self.assertIn('application="park"', xml)
        self.assertIn('mono 16k pipecat {} true true 16000', xml)

    def test_create_extension_action(self):
        action = self.agent.create_extension()
        self.assertEqual(action['res_model'], 'connect.freeswitch.exten')
        self.assertEqual(
            action['context']['default_dst'],
            'connect.pipecat.agent,%s' % self.agent.id,
        )

    def test_exten_destination_selection(self):
        selection = dict(
            self.env['connect.freeswitch.exten']._fields['dst'].selection,
        )
        self.assertEqual(selection['connect.pipecat.agent'], 'AI Agent')

    def test_connect_user_is_read_only(self):
        user = new_test_user(
            self.env, login='pipecat-read-only',
            groups='base.group_user,connect.group_user',
        )
        record = self.agent.with_user(user)
        self.assertEqual(record.name, 'Reception')
        with self.assertRaises(AccessError):
            record.write({'name': 'Changed'})


@tagged('post_install', '-at_install', 'connect_pipecat')
class TestPipecatAPI(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.settings = cls.env['connect.settings'].sudo()
        cls.token = cls.settings.get_param('pipecat_service_token')
        cls.settings.set_param('openai_api_key', 'openai-test-key')
        cls.agent = cls.env['connect.pipecat.agent'].create({
            'name': 'API Agent',
            'system_prompt': 'Be concise.',
            'stt_provider': 'openai',
            'llm_provider': 'openai',
            'tts_provider': 'openai',
        })
        cls.transfer_exten = cls.env['connect.freeswitch.exten'].create({
            'number': '9200',
        })
        cls.agent.transfer_exten = cls.transfer_exten
        cls.call = cls.env['connect.call'].create({
            'caller': '+15550000001',
            'called': '9100',
            'status': 'completed',
            'direction': 'incoming',
        })
        cls.channel = cls.env['connect.channel'].create({
            'sid': 'pipecat-call-uuid',
            'call': cls.call.id,
            'caller': '+15550000001',
            'called': '9100',
            'status': 'completed',
            'technical_direction': 'inbound',
        })
        cls.recording = cls.env['connect.recording'].with_context(
            skip_transcription=True,
        ).create({
            'call': cls.call.id,
            'channel': cls.channel.id,
            'call_sid': cls.channel.sid,
            'status': 'completed',
            'source': 'freeswitch',
        })

    def _headers(self, token=None):
        return {
            'Authorization': 'Bearer %s' % (token or self.token),
            'Content-Type': 'application/json',
        }

    def _post(self, path, payload, token=None):
        return self.opener.post(
            self.base_url() + path,
            data=json.dumps(payload), headers=self._headers(token),
        )

    def test_agent_rejects_missing_and_wrong_bearer(self):
        response = self.url_open('/pipecat/agent/%s' % self.agent.id)
        self.assertEqual(response.status_code, 401)
        response = self.url_open(
            '/pipecat/agent/%s' % self.agent.id,
            headers=self._headers('wrong-token'),
        )
        self.assertEqual(response.status_code, 401)

    def test_agent_config_returns_selected_provider_key(self):
        response = self.url_open(
            '/pipecat/agent/%s' % self.agent.id,
            headers=self._headers(),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['llm']['provider'], 'openai')
        self.assertEqual(data['llm']['api_key'], 'openai-test-key')
        self.assertNotIn('anthropic_api_key', response.text)

    def test_call_result_updates_call_and_recording(self):
        response = self._post('/pipecat/call-result', {
            'call_uuid': self.channel.sid,
            'transcript': 'Caller: Hello\nAgent: Hi',
            'summary': 'The caller said hello.',
        })
        self.assertEqual(response.status_code, 200)
        self.recording.invalidate_recordset()
        self.call.invalidate_recordset()
        self.assertEqual(self.recording.transcript, 'Caller: Hello\nAgent: Hi')
        self.assertIn('The caller said hello.', str(self.recording.summary))
        self.assertIn('The caller said hello.', str(self.call.summary))
        self.assertFalse(self.recording.transcription_pending)

    def test_transfer_stops_fork_then_transfers(self):
        calls = []

        def fake_api(_settings, command, args=''):
            calls.append((command, args))
            return '+OK'

        with mock.patch.object(
                type(self.env['connect.settings']), 'freeswitch_api', fake_api):
            response = self._post('/pipecat/transfer', {
                'call_uuid': self.channel.sid,
                'agent_id': self.agent.id,
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, [
            ('uuid_audio_fork', '%s stop' % self.channel.sid),
            ('uuid_transfer', '%s %s' % (
                self.channel.sid, self.transfer_exten.number,
            )),
        ])
