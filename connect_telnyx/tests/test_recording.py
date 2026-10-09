from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from odoo.exceptions import ValidationError
from odoo.tests import HttpCase, tagged

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
        self.assertEqual(recording.telnyx_recording_id, 'recording-1')
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


@tagged('post_install', '-at_install')
class TestTelnyxRecordingLinks(TelnyxTestCommon):
    """Telnyx signs every recording link for 10 minutes only.

    The player must point at the proxy route (no API call while rendering)
    and a fresh link must be requested when the audio is actually fetched.
    """

    STALE_URL = (
        'https://s3.eu-central-1.amazonaws.com/telephony-recorder-prod-fr5/'
        'rec.mp3?X-Amz-Expires=600&X-Amz-Signature=stale')
    FRESH_URL = (
        'https://s3.eu-central-1.amazonaws.com/telephony-recorder-prod-fr5/'
        'rec.mp3?X-Amz-Expires=600&X-Amz-Signature=fresh')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.settings = cls.env['connect.settings'].sudo()
        cls.call = cls.env['connect.call'].create({
            'caller': '+15550001111',
            'called': '+15550002222',
            'direction': 'incoming',
            'status': 'completed',
        })
        cls.channel = cls.env['connect.channel'].create({
            'call': cls.call.id,
            'sid': 'v3:voicemail-call-sid',
            'caller': cls.call.caller,
            'called': cls.call.called,
            'technical_direction': 'inbound',
            'status': 'completed',
            'call_type': 'phone',
        })

    def _recording(self, **vals):
        values = {
            'sid': '3f8a7c2e-0b1d-4e5f-9a6b-7c8d9e0f1a2b',
            'telnyx_recording_id': '3f8a7c2e-0b1d-4e5f-9a6b-7c8d9e0f1a2b',
            'media_url': self.STALE_URL,
        }
        values.update(vals)
        return self.env['connect.recording'].with_context(
            skip_transcription=True).create(values)

    def _patch_api(self, **kwargs):
        return patch.object(
            type(self.settings), 'telnyx_api_request', autospec=True,
            **kwargs)

    def test_player_points_at_proxy_without_api_call(self):
        recording = self._recording()
        proxy_url = '/connect/recording/{}'.format(recording.id)
        with self._patch_api(side_effect=AssertionError('API called')) as api:
            for proxy_recordings in (False, True):
                self.settings.set_param('proxy_recordings', proxy_recordings)
                recording.invalidate_recordset(['recording_widget'])
                self.assertIn(proxy_url, recording.recording_widget)
                self.assertNotIn('X-Amz-Signature', recording.recording_widget)
            self.call.invalidate_recordset(['recording_widget'])
            recording.call = self.call
            self.assertIn(proxy_url, self.call.recording_widget)
        api.assert_not_called()

    def test_download_requests_fresh_link(self):
        recording = self._recording()
        with self._patch_api(return_value={
                'data': {'download_urls': {'mp3': self.FRESH_URL}}}) as api:
            self.assertEqual(
                recording._get_media_download_url(), self.FRESH_URL)
        api.assert_called_once_with(
            self.settings, 'GET', 'recordings/{}'.format(
                recording.telnyx_recording_id))

    def test_download_falls_back_to_stored_link_on_api_error(self):
        recording = self._recording()
        with self._patch_api(side_effect=ValidationError('down')):
            self.assertEqual(
                recording._get_media_download_url(), self.STALE_URL)

    def test_attachment_recording_is_served_from_odoo(self):
        recording = self._recording(
            recording_attachment='YXVkaW8=', recording_filename='ai.mp3')
        with self._patch_api(side_effect=AssertionError('API called')):
            self.assertEqual(
                recording._get_media_src(False),
                recording.get_attachment_media_url())
            self.assertEqual(
                recording._get_media_download_url(), self.STALE_URL)

    def test_other_provider_recording_keeps_core_behavior(self):
        recording = self._recording(
            sid='RE0123', telnyx_recording_id=False,
            media_url='https://api.twilio.com/RE0123')
        self.settings.set_param('proxy_recordings', False)
        with self._patch_api(side_effect=AssertionError('API called')):
            self.assertEqual(
                recording._get_media_src(False),
                'https://api.twilio.com/RE0123')
            self.assertEqual(
                recording._get_media_download_url(),
                'https://api.twilio.com/RE0123')

    def test_voicemail_stores_recording_id_and_refreshes_link(self):
        self.env['connect.call'].on_telnyx_vm_recording_status({
            'CallSid': self.channel.sid,
            'RecordingSid': 'vm-recording-1',
            'RecordingUrl': self.STALE_URL,
            'RecordingDuration': '7',
        })
        self.assertEqual(
            self.call.telnyx_voicemail_recording_id, 'vm-recording-1')
        self.settings.set_param('proxy_recordings', False)
        with self._patch_api(side_effect=AssertionError('API called')):
            self.call.invalidate_recordset(['voicemail_widget'])
            self.assertIn(
                '/connect/voicemail/{}'.format(self.call.id),
                self.call.voicemail_widget)
        with self._patch_api(return_value={
                'data': {'download_urls': {'mp3': self.FRESH_URL}}}) as api:
            self.assertEqual(
                self.call._get_voicemail_download_url(), self.FRESH_URL)
        api.assert_called_once_with(
            self.settings, 'GET', 'recordings/vm-recording-1')


@tagged('post_install', '-at_install')
class TestTelnyxRecordingProxy(HttpCase):
    """The proxy route downloads through a link requested at playback."""

    FRESH_URL = 'https://s3.example.test/rec.mp3?X-Amz-Signature=fresh'

    def test_proxy_route_serves_fresh_link(self):
        recording = self.env['connect.recording'].with_context(
            skip_transcription=True).create({
                'sid': '3f8a7c2e-0b1d-4e5f-9a6b-7c8d9e0f1a2b',
                'telnyx_recording_id': '3f8a7c2e-0b1d-4e5f-9a6b-7c8d9e0f1a2b',
                'media_url': 'https://s3.example.test/rec.mp3'
                             '?X-Amz-Signature=stale',
            })
        settings = self.env['connect.settings']
        served = []

        def serve(controller, media_url):
            served.append(media_url)
            return 'audio'

        from odoo.addons.connect.controllers.main import ConnectController
        self.authenticate('admin', 'admin')
        with patch.object(
                type(settings), 'telnyx_get_recording_download_url',
                autospec=True, return_value=self.FRESH_URL), \
                patch.object(ConnectController, '_serve_media', serve):
            response = self.url_open(
                '/connect/recording/{}'.format(recording.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(served, [self.FRESH_URL])
