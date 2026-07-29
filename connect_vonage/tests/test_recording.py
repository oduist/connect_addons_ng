# -*- coding: utf-8 -*-
"""Recording flow tests: JWT-authenticated download into the attachment
and attachment-based transcription (ADR-036)."""
import base64
from unittest.mock import MagicMock, patch

from odoo.tests import tagged

from .common import VonageTestCommon


def recording_event(recording_url='https://api.nexmo.com/v1/files/rec-1',
                    recording_uuid='rec-uuid-1',
                    conversation_uuid='conv-rec-1', **kwargs):
    event = {
        'recording_url': recording_url,
        'recording_uuid': recording_uuid,
        'conversation_uuid': conversation_uuid,
        'start_time': '2026-07-11T10:00:00Z',
        'end_time': '2026-07-11T10:01:00Z',
        'size': 12345,
        'timestamp': '2026-07-11T10:01:01Z',
    }
    event.update(kwargs)
    return event


def download_side_effect(url, file_path):
    with open(file_path, 'wb') as f:
        f.write(b'audio-bytes')


@tagged('at_install', '-post_install')
class TestVonageRecording(VonageTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.call = cls.env['connect.call'].with_context(
            tracking_disable=True).create({
                'caller': '+15550002222',
                'called': '+15550001111',
                'status': 'completed',
                'direction': 'incoming',
                'partner': cls.partner.id,
            })
        cls.channel = cls.env['connect.channel'].with_context(
            tracking_disable=True).create({
                'sid': 'leg-rec-1',
                'conversation_uuid': 'conv-rec-1',
                'caller': '+15550002222',
                'called': '+15550001111',
                'status': 'completed',
                'technical_direction': 'inbound',
                'call': cls.call.id,
            })

    def test_on_recording_event_queues_attachment_download(self):
        self.env['connect.recording'].on_recording_event(recording_event())
        rec = self.env['connect.recording'].search(
            [('sid', '=', 'rec-uuid-1')])
        self.assertFalse(rec.vonage_downloaded)
        with self.mock_vonage_client() as client:
            client.voice.download_recording.side_effect = \
                download_side_effect
            self.env['connect.recording']._cron_download_vonage_recordings()
        self.assertTrue(rec)
        self.assertEqual(rec.call, self.call)
        self.assertEqual(rec.channel, self.channel)
        self.assertEqual(rec.call_sid, 'leg-rec-1')
        self.assertEqual(rec.duration, 60)
        self.assertFalse(rec.media_url)
        self.assertTrue(rec.vonage_downloaded)
        self.assertEqual(
            base64.b64decode(rec.recording_attachment), b'audio-bytes')
        # Transcription is off by default in the test settings.
        self.assertFalse(rec.transcription_pending)

    def test_download_failure_then_cron_retry(self):
        self.env['connect.recording'].on_recording_event(
            recording_event(recording_uuid='rec-uuid-2'))
        with self.mock_vonage_client() as client:
            client.voice.download_recording.side_effect = \
                Exception('network down')
            self.env['connect.recording']._cron_download_vonage_recordings()
        rec = self.env['connect.recording'].search(
            [('sid', '=', 'rec-uuid-2')])
        self.assertFalse(rec.vonage_downloaded)
        self.assertFalse(rec.recording_attachment)
        with self.mock_vonage_client() as client:
            client.voice.download_recording.side_effect = \
                download_side_effect
            self.env['connect.recording']._cron_download_vonage_recordings()
        self.assertTrue(rec.vonage_downloaded)
        self.assertEqual(
            base64.b64decode(rec.recording_attachment), b'audio-bytes')

    def test_voicemail_recording_source(self):
        self.env['connect.recording'].on_vm_recording_event(
            recording_event(recording_uuid='rec-vm-1'))
        rec = self.env['connect.recording'].search(
            [('sid', '=', 'rec-vm-1')])
        self.assertEqual(rec.source, 'voicemail')

    def test_recording_retry_is_idempotent(self):
        params = recording_event(recording_uuid='rec-retry-1')
        self.env['connect.recording'].on_recording_event(params)
        self.env['connect.recording'].on_recording_event(params)
        recordings = self.env['connect.recording'].search(
            [('sid', '=', 'rec-retry-1')])
        self.assertEqual(len(recordings), 1)

    def test_transcribe_from_attachment(self):
        rec = self.env['connect.recording'].with_context(
            skip_transcription=True).create({
                'sid': 'rec-tr-1',
                'call': self.call.id,
                'recording_attachment': base64.b64encode(b'audio-bytes'),
                'recording_filename': 'rec-tr-1.mp3',
                'vonage_downloaded': True,
            })
        self.settings.set_param('openai_api_key', 'sk-test')
        mock_client = MagicMock()
        segment = MagicMock()
        segment.start = 0
        segment.text = 'Hello world'
        mock_transcript = MagicMock()
        mock_transcript.segments = [segment]
        mock_client.audio.transcriptions.create.return_value = \
            mock_transcript
        mock_summary = MagicMock()
        mock_summary.choices = [MagicMock()]
        mock_summary.choices[0].message.content = 'A greeting'
        mock_client.chat.completions.create.return_value = mock_summary
        with patch.object(
            type(self.env['connect.settings']),
            'get_openai_client',
            return_value=mock_client,
        ):
            rec.get_transcript()
        self.assertIn('Hello world', rec.transcript)
        self.assertFalse(rec.transcription_error)
