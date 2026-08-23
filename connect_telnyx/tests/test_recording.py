from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from odoo.tests import tagged

from odoo.addons.connect_telnyx.models.utils import (
    REDACTED,
    redact_telnyx_debug_payload,
)

from .common import TelnyxTestCommon


@tagged('post_install', '-at_install')
class TestTelnyxRecording(TelnyxTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.settings = cls.env['connect.settings'].sudo()
        cls.settings.set_param('debug_mode', True)
        cls.call = cls.env['connect.call'].create({
            'caller': '+15550001111',
            'called': '+15550002222',
            'direction': 'incoming',
            'status': 'completed',
        })
        cls.channel = cls.env['connect.channel'].create({
            'call': cls.call.id,
            'sid': 'v3:webhook-call-sid',
            'caller': cls.call.caller,
            'called': cls.call.called,
            'technical_direction': 'inbound',
            'status': 'completed',
            'call_type': 'phone',
        })

    def _recording_client(self, media_url):
        client = MagicMock()
        client.recordings.retrieve.return_value = SimpleNamespace(
            data=SimpleNamespace(
                id='recording-1',
                call_control_id=None,
                call_leg_id='uuid-api-leg-id',
                download_urls=SimpleNamespace(mp3=media_url, wav=None),
                duration_millis=9000,
                source='call',
                status='completed',
            )
        )
        return client

    def test_debug_payload_redacts_recording_url_without_mutation(self):
        payload = {
            'CallSid': 'v3:test',
            'nested': {'recording_url': 'https://example.test/signed'},
        }

        safe_payload = redact_telnyx_debug_payload(payload)

        self.assertEqual(safe_payload['nested']['recording_url'], REDACTED)
        self.assertEqual(
            payload['nested']['recording_url'],
            'https://example.test/signed',
        )

    def test_recording_keeps_webhook_call_and_channel_links(self):
        webhook_url = (
            'https://example.test/webhook.mp3?X-Amz-Signature=webhook-secret'
        )
        api_url = 'https://example.test/api.mp3?X-Amz-Signature=api-secret'
        params = {
            'RecordingSid': 'recording-1',
            'CallSid': self.channel.sid,
            'RecordingUrl': webhook_url,
            'RecordingDuration': '10',
            'RecordingStatus': 'completed',
        }

        with patch.object(
            type(self.settings),
            'get_telnyx_client',
            autospec=True,
            return_value=self._recording_client(api_url),
        ):
            self.env['connect.recording'].on_telnyx_recording_status(params)

        recording = self.env['connect.recording'].search([
            ('sid', '=', 'recording-1'),
        ])
        self.assertEqual(recording.call, self.call)
        self.assertEqual(recording.channel, self.channel)
        self.assertEqual(recording.call_sid, self.channel.sid)
        self.assertEqual(recording.media_url, api_url)
        self.assertEqual(self.call.recording, recording)

        debug_record = self.env['connect.debug'].search([
            ('message', 'ilike', 'On recording status'),
        ], order='id desc', limit=1)
        self.assertTrue(debug_record)
        self.assertIn('"RecordingUrl": "{}"'.format(REDACTED),
                      debug_record.message)
        self.assertNotIn('X-Amz-Signature', debug_record.message)

    def test_call_status_debug_redacts_recording_url(self):
        signed_url = (
            'https://example.test/call.mp3?X-Amz-Signature=call-secret'
        )
        params = {
            'CallSid': 'v3:status-call',
            'From': '+15550001111',
            'To': '+15550002222',
            'CallStatus': 'completed',
            'RecordingUrl': signed_url,
        }
        channel_model = self.env['connect.channel']

        with patch.object(
            type(channel_model),
            'process_channel_event',
            autospec=True,
            return_value=self.channel,
        ):
            channel_model.on_telnyx_call_status(params)

        debug_record = self.env['connect.debug'].search([
            ('message', 'ilike', 'On channel status'),
        ], order='id desc', limit=1)
        self.assertIn('"RecordingUrl": "{}"'.format(REDACTED),
                      debug_record.message)
        self.assertNotIn('X-Amz-Signature', debug_record.message)
