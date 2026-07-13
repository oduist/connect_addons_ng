import json

from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestLivekitAgentWebhooks(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['connect.settings'].sudo().set_param(
            'api_url', cls.base_url())
        cls.agent = cls.env['connect.livekit.agent'].create({
            'name': 'A', 'instructions': 'x', 'enable_contact_tools': True,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Caller', 'phone': '+15557778888',
        })

    def _post(self, path, payload, token):
        return self.opener.post(
            self.base_url() + path,
            data=json.dumps(payload),
            headers={'X-Odoo-LiveKit-Token': token,
                     'Content-Type': 'application/json'})

    def test_tool_wrong_token_403(self):
        resp = self._post(
            '/livekit/webhook/agent/{}/tool/lookup_contact'.format(
                self.agent.id),
            {'phone': self.partner.phone}, 'wrong')
        self.assertEqual(resp.status_code, 403)

    def test_tool_lookup_contact(self):
        resp = self._post(
            '/livekit/webhook/agent/{}/tool/lookup_contact'.format(
                self.agent.id),
            {'phone': self.partner.phone}, self.agent.sudo().tool_token)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['found'])
        self.assertEqual(data['partner_id'], self.partner.id)

    def test_transcript_creates_ai_recording(self):
        call = self.env['connect.call'].create({
            'caller': '+15557778888', 'called': '+15550001111',
            'direction': 'incoming', 'livekit_room_name': 'ai-out-web',
        })
        resp = self._post(
            '/livekit/webhook/agent/{}/transcript'.format(self.agent.id),
            {'room_name': 'ai-out-web',
             'messages': [{'role': 'user', 'text': 'Hello'}],
             'summary': 'A short call', 'duration_secs': 5},
            self.agent.sudo().tool_token)
        self.assertEqual(resp.status_code, 200)
        rec = self.env['connect.recording'].sudo().search(
            [('call', '=', call.id), ('source', '=', 'livekit-ai')], limit=1)
        self.assertTrue(rec)
        self.assertFalse(rec.transcription_pending)
