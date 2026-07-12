from unittest.mock import MagicMock

from odoo.tests import tagged
from odoo.exceptions import ValidationError

from .common import LivekitTestCommon


@tagged('at_install', '-post_install')
class TestLivekitRoom(LivekitTestCommon):

    def test_create_generates_room_name_and_token(self):
        room = self.env['connect.livekit.room'].create({'name': 'Standup'})
        self.assertTrue(room.room_name.startswith('meet-'))
        self.assertTrue(room.sudo().guest_token)

    def test_public_url(self):
        room = self.env['connect.livekit.room'].create({'name': 'Demo'})
        self.assertIn('/livekit/meet/', room.public_url)
        self.assertIn(room.sudo().guest_token, room.public_url)

    def test_ensure_room_sets_active(self):
        room = self.env['connect.livekit.room'].create({'name': 'Demo'})
        with self.mock_api(return_value=MagicMock(sid='RM_1')):
            room._ensure_livekit_room()
        self.assertEqual(room.state, 'active')
        self.assertEqual(room.sid, 'RM_1')

    def test_start_recording_stores_egress(self):
        room = self.env['connect.livekit.room'].create(
            {'name': 'Demo', 'state': 'active'})
        with self.mock_api(return_value=MagicMock(egress_id='EG_1')):
            room.action_start_recording()
        self.assertEqual(room.egress_sid, 'EG_1')
        self.assertTrue(room.record)

    def test_start_recording_twice_raises(self):
        room = self.env['connect.livekit.room'].create(
            {'name': 'Demo', 'state': 'active', 'egress_sid': 'EG_1'})
        with self.assertRaises(ValidationError):
            room.action_start_recording()

    def test_close_marks_finished(self):
        room = self.env['connect.livekit.room'].create(
            {'name': 'Demo', 'state': 'active'})
        with self.mock_api():
            room.action_close()
        self.assertEqual(room.state, 'finished')

    def test_get_room_by_guest_token(self):
        room = self.env['connect.livekit.room'].create({'name': 'Demo'})
        found = self.env['connect.livekit.room'].get_room_by_guest_token(
            room.sudo().guest_token)
        self.assertEqual(found, room)
        self.assertFalse(
            self.env['connect.livekit.room'].get_room_by_guest_token('nope'))
