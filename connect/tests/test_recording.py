from unittest.mock import patch, MagicMock

from odoo.tests import tagged
from odoo.exceptions import ValidationError

from .common import ConnectTestCommon


@tagged('at_install', '-post_install')
class TestRecording(ConnectTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.call = cls._create_call(
            caller='+15551111111',
            called='+15552222222',
            status='completed',
            duration=60,
        )
        cls.recording = cls.env['connect.recording'].with_context(
            skip_transcription=True,
        ).create({
            'call': cls.call.id,
            'media_url': 'https://example.com/recording.mp3',
            'duration': 60,
            'status': 'completed',
            'caller_number': '+15551111111',
            'called_number': '+15552222222',
        })

    def test_create_recording(self):
        """Test basic recording creation."""
        self.assertTrue(self.recording.id)
        self.assertEqual(self.recording.duration, 60)

    def test_duration_human(self):
        """Test duration_human computes HH:MM."""
        self.assertEqual(self.recording.duration_human, '01:00')

    def test_duration_human_zero(self):
        """Test duration_human for zero."""
        rec = self.env['connect.recording'].with_context(
            skip_transcription=True).create({
            'duration': 0,
        })
        self.assertEqual(rec.duration_human, '00:00')

    def test_recording_widget_with_media_url(self):
        """Test recording widget generates audio tag with proxy URL."""
        widget = self.recording.recording_widget
        self.assertIn('<audio', widget)
        self.assertIn('/connect/recording/', widget)

    def test_recording_widget_without_media(self):
        """Test recording widget is empty without media."""
        rec = self.env['connect.recording'].with_context(
            skip_transcription=True).create({})
        self.assertEqual(rec.recording_widget, '')

    def test_list_view_summary(self):
        """Test list_view_summary mirrors summary."""
        self.recording.summary = '<p>Test Summary</p>'
        self.recording.invalidate_recordset()
        self.assertEqual(self.recording.list_view_summary, self.recording.summary)

    def test_sync_summary_to_call(self):
        """Test summary constraint syncs summary to linked call."""
        self.recording.summary = '<p>Synced Summary</p>'
        self.assertEqual(self.call.summary, self.recording.summary)

    def test_get_transcript_no_key(self):
        """Test get_transcript raises ValidationError without API key."""
        with self.assertRaises(ValidationError):
            self.recording.get_transcript()

    def test_get_transcript_no_key_silent(self):
        """Test get_transcript returns False silently without API key."""
        result = self.recording.get_transcript(fail_silently=True)
        self.assertFalse(result)

    def test_get_transcript_no_media_url(self):
        """Test get_transcript raises when no media_url."""
        rec = self.env['connect.recording'].with_context(
            skip_transcription=True).create({})
        self.env['connect.settings'].set_param('openai_api_key', 'test-key')
        with self.assertRaises(ValidationError):
            rec.get_transcript()

    def test_transcribe_recording_mock(self):
        """Test transcribe_recording with mocked OpenAI."""
        with self.mock_openai_client(summary_text='<p>AI Summary</p>'):
            with patch('odoo.addons.connect.models.recording.requests.get') as mock_get:
                mock_response = MagicMock()
                mock_response.raise_for_status = MagicMock()
                mock_response.iter_content = MagicMock(return_value=[b'audio_data'])
                mock_get.return_value = mock_response

                self.recording.transcribe_recording('test-key', 'Summarize this')
                self.assertEqual(self.recording.summary, '<p>AI Summary</p>')

    def test_update_transcript(self):
        """Test update_transcript writes transcript and summary."""
        with self.mock_connect_reload_view():
            self.recording.update_transcript({
                'transcript': 'Hello world',
                'summary': '<p>Summary</p>',
                'transcription_price': 0.05,
            })
        self.assertEqual(self.recording.transcript, 'Hello world')
        self.assertEqual(self.recording.summary, '<p>Summary</p>')
        self.assertEqual(self.recording.transcription_price, '0.05')

    def test_update_transcript_syncs_to_call(self):
        """Test update_transcript updates linked call summary."""
        with self.mock_connect_reload_view():
            self.recording.update_transcript({
                'transcript': 'Test',
                'summary': '<p>Call Summary</p>',
            })
        self.assertEqual(self.call.summary, '<p>Call Summary</p>')

    def test_create_with_transcription_enabled(self):
        """Test create triggers transcription when enabled."""
        self.env['connect.settings'].set_param('transcript_calls', True)
        self.env['connect.settings'].set_param('openai_api_key', 'test-key')
        with self.mock_openai_client():
            with patch('odoo.addons.connect.models.recording.requests.get') as mock_get:
                mock_response = MagicMock()
                mock_response.raise_for_status = MagicMock()
                mock_response.iter_content = MagicMock(return_value=[b'data'])
                mock_get.return_value = mock_response

                rec = self.env['connect.recording'].create({
                    'media_url': 'https://example.com/test.mp3',
                    'duration': 10,
                })
                self.assertTrue(rec.id)
