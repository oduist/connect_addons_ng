from odoo.tests import tagged

from .common import ConnectTestCommon


@tagged('at_install', '-post_install')
class TestMessage(ConnectTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.message = cls.env['connect.message'].create({
            'from_number': '+15551111111',
            'to_number': '+15552222222',
            'body': 'Hello World',
            'status': 'received',
        })

    def test_create_message(self):
        """Test basic message creation."""
        self.assertTrue(self.message.id)
        self.assertEqual(self.message.from_number, '+15551111111')
        self.assertEqual(self.message.to_number, '+15552222222')

    def test_message_type_auto_sms(self):
        """Test message_type defaults to sms when no media."""
        self.assertEqual(self.message.message_type, 'sms')

    def test_message_type_auto_mms(self):
        """Test message_type is mms when media present."""
        msg = self.env['connect.message'].create({
            'from_number': '+15551111111',
            'to_number': '+15552222222',
            'body': 'Photo',
            'num_media': 1,
            'status': 'received',
        })
        self.assertEqual(msg.message_type, 'mms')

    def test_direction_incoming(self):
        """Test direction is incoming for received messages."""
        self.assertEqual(self.message.direction, 'incoming')

    def test_direction_outgoing_with_sender(self):
        """Test direction is outgoing when sender_user is set."""
        msg = self.env['connect.message'].create({
            'from_number': '+15551111111',
            'to_number': '+15552222222',
            'body': 'Out',
            'sender_user': self.admin_user.id,
            'status': 'sent',
        })
        self.assertEqual(msg.direction, 'outgoing')

    def test_direction_display_incoming(self):
        """Test incoming direction shows down arrow."""
        self.assertIn('fa-arrow-down', self.message.direction_display)

    def test_direction_display_outgoing(self):
        """Test outgoing direction shows up arrow."""
        msg = self.env['connect.message'].create({
            'from_number': '+15551111111',
            'to_number': '+15552222222',
            'body': 'Out',
            'sender_user': self.admin_user.id,
            'status': 'sent',
        })
        self.assertIn('fa-arrow-up', msg.direction_display)

    def test_status_display_sent(self):
        """Test sent status shows paper-plane icon."""
        msg = self.env['connect.message'].create({
            'from_number': '+15551111111',
            'to_number': '+15552222222',
            'status': 'sent',
        })
        self.assertIn('paper-plane', msg.status_display)

    def test_status_display_delivered(self):
        """Test delivered status shows check icon."""
        msg = self.env['connect.message'].create({
            'from_number': '+15551111111',
            'to_number': '+15552222222',
            'status': 'delivered',
        })
        self.assertIn('check-circle', msg.status_display)

    def test_status_display_failed(self):
        """Test failed status shows times icon."""
        msg = self.env['connect.message'].create({
            'from_number': '+15551111111',
            'to_number': '+15552222222',
            'status': 'failed',
        })
        self.assertIn('times-circle', msg.status_display)

    def test_name_compute(self):
        """Test computed name includes type, number and date."""
        name = self.message.name
        self.assertIn('sms', name)
        self.assertIn('+1 555-111-1111', name)

    def test_name_new_record(self):
        """Test name for record without create_date."""
        msg = self.env['connect.message'].new({
            'from_number': '+15551111111',
            'to_number': '+15552222222',
            'message_type': 'sms',
        })
        self.assertIn('New', msg.name)

    def test_format_phone_number(self):
        """Test static phone number formatting."""
        result = self.env['connect.message']._format_phone_number('+15551234567')
        self.assertIn('555', result)

    def test_format_phone_number_invalid(self):
        """Test invalid number returns original."""
        result = self.env['connect.message']._format_phone_number('invalid')
        self.assertEqual(result, 'invalid')

    def test_format_phone_number_none(self):
        """Test None returns None."""
        result = self.env['connect.message']._format_phone_number(None)
        self.assertIsNone(result)

    def test_ref_compute(self):
        """Test reference field computes from res_model/res_id."""
        msg = self.env['connect.message'].create({
            'from_number': '+15551111111',
            'to_number': '+15552222222',
            'status': 'received',
            'res_model': 'res.partner',
            'res_id': self.partner.id,
        })
        self.assertTrue(msg.ref)
        self.assertEqual(msg.ref._name, 'res.partner')

    def test_ref_empty(self):
        """Test ref is False without res_model/res_id."""
        self.assertFalse(self.message.ref)

    def test_get_receive_message_values(self):
        """Test webhook params extraction."""
        params = {
            'MessageSid': 'SM123',
            'From': '+15551111111',
            'To': '+15552222222',
            'Body': 'Test',
            'NumMedia': '0',
            'SmsStatus': 'received',
        }
        vals = self.message.get_receive_message_values(params)
        self.assertEqual(vals['message_sid'], 'SM123')
        self.assertEqual(vals['from_number'], '+15551111111')
        self.assertEqual(vals['to_number'], '+15552222222')
        self.assertEqual(vals['body'], 'Test')
        self.assertEqual(vals['num_media'], 0)

    def test_media_widget_image(self):
        """Test media widget renders image tag for image content type."""
        msg = self.env['connect.message'].create({
            'from_number': '+15551111111',
            'to_number': '+15552222222',
            'status': 'received',
            'media_url': 'https://example.com/image.jpg',
            'media_content_type': 'image/jpeg',
        })
        self.assertIn('<img', msg.media_widget)

    def test_media_widget_audio(self):
        """Test media widget renders audio tag."""
        msg = self.env['connect.message'].create({
            'from_number': '+15551111111',
            'to_number': '+15552222222',
            'status': 'received',
            'media_url': 'https://example.com/audio.mp3',
            'media_content_type': 'audio/mpeg',
        })
        self.assertIn('<audio', msg.media_widget)

    def test_media_widget_video(self):
        """Test media widget renders video tag."""
        msg = self.env['connect.message'].create({
            'from_number': '+15551111111',
            'to_number': '+15552222222',
            'status': 'received',
            'media_url': 'https://example.com/video.mp4',
            'media_content_type': 'video/mp4',
        })
        self.assertIn('<video', msg.media_widget)

    def test_media_widget_download(self):
        """Test media widget renders download link for unknown type."""
        msg = self.env['connect.message'].create({
            'from_number': '+15551111111',
            'to_number': '+15552222222',
            'status': 'received',
            'media_url': 'https://example.com/file.pdf',
            'media_content_type': 'application/pdf',
        })
        self.assertIn('Download media', msg.media_widget)

    def test_media_widget_javascript_url_not_rendered(self):
        """A javascript: media_url (attacker-controlled MediaUrl0) must not
        become a clickable link in the sanitize=False Html field: escaping
        stops attribute breakout but not the scheme, so only http/https URLs
        are rendered."""
        msg = self.env['connect.message'].create({
            'from_number': '+15551111111',
            'to_number': '+15552222222',
            'status': 'received',
            'media_url': 'javascript:alert(1)',
            'media_content_type': 'application/pdf',
        })
        widget = msg.media_widget or ''
        self.assertNotIn('javascript:', widget)
        self.assertNotIn('<a', widget)
        self.assertEqual(widget, '')

    def test_media_widget_data_url_not_rendered(self):
        """Same allowlist blocks other dangerous schemes (data:)."""
        msg = self.env['connect.message'].create({
            'from_number': '+15551111111',
            'to_number': '+15552222222',
            'status': 'received',
            'media_url': 'data:text/html,<script>alert(1)</script>',
            'media_content_type': 'image/png',
        })
        widget = msg.media_widget or ''
        self.assertNotIn('data:text/html', widget)
        self.assertEqual(widget, '')

    def test_media_widget_empty(self):
        """Test media widget empty without URL."""
        self.assertEqual(self.message.media_widget, '')

    def test_default_status(self):
        """Test default status is draft."""
        msg = self.env['connect.message'].create({
            'from_number': '+15551111111',
            'to_number': '+15552222222',
        })
        self.assertEqual(msg.status, 'draft')

    def test_action_retry_non_failed(self):
        """Test action_retry on non-failed message returns True."""
        result = self.message.action_retry()
        self.assertTrue(result)
