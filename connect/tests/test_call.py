from unittest.mock import patch

from odoo.tests import tagged

from .common import ConnectTestCommon


@tagged('at_install', '-post_install')
class TestCall(ConnectTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.call = cls._create_call(
            caller='+15551111111',
            called='+15552222222',
            duration=125,
            status='completed',
        )

    def test_create_call(self):
        """Test basic call creation."""
        self.assertTrue(self.call.id)
        self.assertEqual(self.call.caller, '+15551111111')
        self.assertEqual(self.call.called, '+15552222222')

    def test_duration_human(self):
        """Test duration_human computes HH:MM from seconds."""
        self.assertEqual(self.call.duration_human, '02:05')

    def test_duration_minutes(self):
        """Test duration_minutes computes float minutes."""
        self.assertAlmostEqual(self.call.duration_minutes, 125 / 60.0, places=2)

    def test_duration_zero(self):
        """Test duration_human for zero seconds."""
        call = self._create_call(duration=0)
        self.assertEqual(call.duration_human, '00:00')

    def test_duration_human_large(self):
        """Test duration_human for > 60 minutes."""
        call = self._create_call(duration=3661)
        self.assertEqual(call.duration_human, '61:01')

    def test_name_compute(self):
        """Test computed name includes status and direction."""
        name = self.call.name
        self.assertIn('Completed', name)

    def test_ref_with_partner(self):
        """Test ref points to partner when set."""
        self.call.partner = self.partner
        self.call.invalidate_recordset()
        ref = self.call.ref
        self.assertTrue(ref)
        self.assertEqual(ref._name, 'res.partner')
        self.assertEqual(ref.id, self.partner.id)

    def test_ref_without_partner(self):
        """Test ref is False when no partner."""
        self.assertFalse(self.call.ref)

    def test_voicemail_icon_with_url(self):
        """Test voicemail icon shows when URL exists."""
        self.call.voicemail_url = 'https://example.com/vm.mp3'
        self.call.invalidate_recordset()
        self.assertIn('fa-envelope-o', self.call.voicemail_icon)

    def test_voicemail_widget_uses_internal_attachment_url_directly(self):
        """Internal voicemail attachment URLs should not be proxied."""
        self.env['connect.settings'].set_param('proxy_recordings', True)
        self.call.voicemail_url = (
            '/web/content?model=connect.recording&id=1'
            '&field=recording_attachment')
        self.call.invalidate_recordset()
        self.assertIn('/web/content?model=connect.recording', self.call.voicemail_widget)
        self.assertNotIn('/connect/voicemail/', self.call.voicemail_widget)

    def test_voicemail_icon_without_url(self):
        """Test voicemail icon is empty without URL."""
        self.assertEqual(self.call.voicemail_icon, '')

    def test_default_call_type(self):
        """Test default call_type is phone."""
        call = self._create_call()
        self.assertEqual(call.call_type, 'phone')

    def test_determine_direction_outbound_api(self):
        """Test outbound-api channels are outgoing."""
        channel = self._create_channel('ch1', technical_direction='outbound-api')
        direction = self.env['connect.call']._determine_direction(channel)
        self.assertEqual(direction, 'outgoing')

    def test_determine_direction_inbound_pbx_user(self):
        """Test inbound with caller PBX user is outgoing (click2call)."""
        connect_user = self._create_connect_user('diruser1')
        channel = self._create_channel(
            'ch2',
            technical_direction='inbound',
            caller_pbx_user=connect_user.id,
        )
        direction = self.env['connect.call']._determine_direction(channel)
        self.assertEqual(direction, 'outgoing')

    def test_determine_direction_inbound_no_user(self):
        """Test inbound without PBX user is incoming."""
        channel = self._create_channel('ch3', technical_direction='inbound')
        direction = self.env['connect.call']._determine_direction(channel)
        self.assertEqual(direction, 'incoming')

    def test_process_call_event_creates_call(self):
        """Test process_call_event creates a call from a first-leg channel."""
        channel = self._create_channel(
            'pce1',
            caller='+15550001111',
            called='+15550002222',
            technical_direction='inbound',
            status='ringing',
        )
        with self.mock_license_check(), self.mock_connect_reload_view():
            call_id = self.env['connect.call'].process_call_event(channel)
        self.assertTrue(call_id)
        self.assertTrue(channel.call)
        self.assertEqual(channel.call.direction, 'incoming')

    def test_process_call_event_no_channel(self):
        """Test process_call_event returns False with no channel."""
        with self.mock_license_check():
            result = self.env['connect.call'].process_call_event(None)
        self.assertFalse(result)

    def test_process_call_event_links_parent(self):
        """Test second-leg channel inherits call from parent."""
        parent = self._create_channel(
            'parent1',
            technical_direction='inbound',
            status='ringing',
        )
        with self.mock_license_check(), self.mock_connect_reload_view():
            self.env['connect.call'].process_call_event(parent)

        child = self._create_channel(
            'child1',
            technical_direction='outbound-dial',
            status='ringing',
            parent_channel=parent.id,
        )
        child.parent_channel = parent
        with self.mock_license_check(), self.mock_connect_reload_view():
            self.env['connect.call'].process_call_event(child)
        self.assertEqual(child.call.id, parent.call.id)

    def test_process_call_event_error_data(self):
        """Test error data is stored on the call."""
        channel = self._create_channel('err1', technical_direction='inbound', status='failed')
        error = {'error_code': '404', 'error_message': 'Not found'}
        with self.mock_license_check(), self.mock_connect_reload_view():
            self.env['connect.call'].process_call_event(channel, error_data=error)
        self.assertTrue(channel.call.has_error)
        self.assertEqual(channel.call.error_code, '404')

    def test_create_partner_button_action(self):
        """Test create_partner_button returns an action window."""
        result = self.call.create_partner_button()
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'res.partner')

    def test_transfer_button_action(self):
        """Test transfer_button returns an action window."""
        result = self.call.transfer_button()
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'connect.transfer_wizard')

    def test_get_widget_fields(self):
        """Test get_widget_fields returns expected fields."""
        fields_list = self.call.get_widget_fields()
        self.assertIn('caller', fields_list)
        self.assertIn('called', fields_list)
        self.assertIn('direction', fields_list)
        self.assertIn('partner', fields_list)

    def test_recording_data_no_recording(self):
        """Test recording data is empty when no recordings."""
        self.assertFalse(self.call.recording)
        self.assertEqual(self.call.transcript, '')
        self.assertEqual(self.call.recording_widget, '')
