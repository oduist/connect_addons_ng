import json

from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestLivekitWebhooks(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.settings = cls.env['connect.settings']
        cls.settings.sudo().set_param('livekit_verify_webhooks', False)
        cls.settings.sudo().set_param('livekit_agent_token', 'agent-secret')
        cls.settings.sudo().set_param('api_url', cls.base_url())

    def test_webhook_unverified_dispatches(self):
        # With verification off any body is accepted and dispatched.
        event = {'event': 'room_started', 'room': {'name': 'meet-x'}}
        resp = self.url_open(
            '/livekit/webhook',
            data=json.dumps(event),
            headers={'Content-Type': 'application/webhook+json'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get('status'), 'ok')

    def test_webhook_verification_rejects_without_key(self):
        self.settings.sudo().set_param('livekit_verify_webhooks', True)
        self.settings.sudo().set_param('livekit_api_key', 'k')
        self.settings.sudo().set_param('livekit_api_secret', 's')
        resp = self.url_open(
            '/livekit/webhook',
            data=json.dumps({'event': 'room_started'}),
            headers={'Content-Type': 'application/webhook+json'})
        # No/invalid Authorization JWT → 403.
        self.assertEqual(resp.status_code, 403)
        self.settings.sudo().set_param('livekit_verify_webhooks', False)

    def test_recording_upload_requires_bearer(self):
        resp = self.url_open(
            '/livekit/webhook/recording/EG_1.ogg',
            data=b'audio-bytes',
            headers={'Content-Type': 'application/octet-stream'})
        self.assertEqual(resp.status_code, 401)

    def test_recording_upload_stores_attachment(self):
        resp = self.opener.put(
            self.base_url() + '/livekit/webhook/recording/EG_up.ogg',
            data=b'audio-bytes',
            headers={'Authorization': 'Bearer agent-secret'})
        self.assertEqual(resp.status_code, 200)
        rec = self.env['connect.recording'].sudo().search(
            [('recording_filename', '=', 'EG_up.ogg')], limit=1)
        self.assertTrue(rec)
        self.assertTrue(rec.recording_attachment)

    def test_agent_config_requires_bearer(self):
        agent = self.env['connect.livekit.agent'].create(
            {'name': 'A', 'instructions': 'x'})
        resp = self.url_open(
            '/livekit/api/agent_config?agent_id={}'.format(agent.id))
        self.assertEqual(resp.status_code, 401)

    def test_agent_config_returns_payload(self):
        agent = self.env['connect.livekit.agent'].create(
            {'name': 'A', 'instructions': 'x'})
        resp = self.url_open(
            '/livekit/api/agent_config?agent_id={}'.format(agent.id),
            headers={'Authorization': 'Bearer agent-secret'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['id'], agent.id)
        self.assertEqual(data['tool_token'], agent.sudo().tool_token)
