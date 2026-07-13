# -*- coding: utf-8 -*-
import base64
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.connect_bird.models.call import BIRD_RECORDING_MAX_ATTEMPTS

from .common import BirdTestCommon, BirdApiMock, FakeResponse, \
    patch_bird_request


@tagged('at_install', '-post_install')
class TestBirdRecording(BirdTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.call = cls.env['connect.call'].sudo().create({
            'caller': '+15550200',
            'called': '+31612345678',
            'status': 'completed',
            'direction': 'outgoing',
            'bird_call_id': 'call-rec-1',
            'bird_recording_pending': True,
        })

    def _patch_download(self, content=b'AUDIO'):
        return patch(
            'odoo.addons.connect_bird.models.recording.httpx.get',
            return_value=FakeResponse(200, content=content))

    def test_cron_fetches_and_stores_recording(self):
        mock = BirdApiMock({
            ('GET', '/voice/calls/call-rec-1/recordings'): {
                'data': [{
                    'id': 'rec-1',
                    'status': 'available',
                    'duration': 42,
                    'format': 'mp3',
                    'url': 'https://s3.example.com/rec-1.mp3?sig=abc',
                }],
            },
        })
        with patch_bird_request(mock), self._patch_download(b'AUDIO'):
            self.env['connect.recording']._cron_fetch_bird_recordings()
        recording = self.env['connect.recording'].search(
            [('sid', '=', 'rec-1')])
        self.assertEqual(len(recording), 1)
        self.assertEqual(recording.call, self.call)
        self.assertEqual(recording.source, 'bird')
        self.assertEqual(recording.duration, 42)
        self.assertEqual(recording.recording_filename, 'rec-1.mp3')
        self.assertEqual(
            base64.b64decode(recording.recording_attachment), b'AUDIO')
        self.assertFalse(self.call.bird_recording_pending)

    def test_cron_retries_until_max_attempts(self):
        mock = BirdApiMock(
            {('GET', '/voice/calls/call-rec-1/recordings'): {'data': []}})
        with patch_bird_request(mock):
            self.env['connect.recording']._cron_fetch_bird_recordings()
            self.assertTrue(self.call.bird_recording_pending)
            self.assertEqual(self.call.bird_recording_attempts, 1)
            self.call.bird_recording_attempts = BIRD_RECORDING_MAX_ATTEMPTS
            self.env['connect.recording']._cron_fetch_bird_recordings()
        self.assertFalse(self.call.bird_recording_pending)

    def test_get_transcript_refreshes_presigned_url(self):
        recording = self.env['connect.recording'].sudo().create({
            'sid': 'rec-2',
            'call_sid': 'call-rec-1',
            'call': self.call.id,
            'source': 'bird',
            'media_url': 'https://s3.example.com/expired',
        })
        mock = BirdApiMock({
            ('GET', '/voice/calls/call-rec-1/recordings'): {
                'data': [{
                    'id': 'rec-2',
                    'url': 'https://s3.example.com/fresh?sig=new',
                }],
            },
        })
        # No OpenAI key configured: core get_transcript exits with False
        # after the Bird override has refreshed the pre-signed URL.
        with patch_bird_request(mock):
            result = recording.get_transcript(fail_silently=True)
        self.assertIs(result, False)
        self.assertEqual(recording.media_url,
                         'https://s3.example.com/fresh?sig=new')
