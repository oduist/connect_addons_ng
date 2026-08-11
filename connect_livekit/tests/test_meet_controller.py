import json
from unittest.mock import patch, MagicMock

from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestLivekitMeetController(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        settings = cls.env['connect.settings'].sudo()
        settings.set_param('api_url', cls.base_url())
        settings.set_param('livekit_ws_url', 'ws://livekit:7880')
        settings.set_param('livekit_api_key', 'k')
        settings.set_param('livekit_api_secret', 's')
        cls.room = cls.env['connect.livekit.room'].create({'name': 'Meet'})

    def test_meet_page_unknown_token_404(self):
        resp = self.url_open('/livekit/meet/deadbeef')
        self.assertEqual(resp.status_code, 404)

    def test_meet_page_renders(self):
        resp = self.url_open(
            '/livekit/meet/{}'.format(self.room.sudo().guest_token))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('lk-meet', resp.text)

    def test_meet_join_returns_token(self):
        with patch.object(
            type(self.env['connect.livekit.room']),
            '_ensure_livekit_room', return_value=MagicMock(),
        ):
            resp = self.opener.post(
                self.base_url() + '/livekit/meet/{}/join'.format(
                    self.room.sudo().guest_token),
                data=json.dumps({'display_name': 'Guest One'}),
                headers={'Content-Type': 'application/json'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['token'])
        self.assertEqual(data['room_name'], self.room.room_name)
        self.assertEqual(data['display_name'], 'Guest One')
