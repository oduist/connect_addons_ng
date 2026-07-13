from unittest.mock import patch

from odoo.tests import tagged

from .common import LivekitTestCommon


@tagged('at_install', '-post_install')
class TestLivekitSettings(LivekitTestCommon):

    def test_api_url_derived_from_ws(self):
        self.settings.sudo().set_param('livekit_api_url', '')
        self.settings.sudo().set_param(
            'livekit_ws_url', 'wss://lk.example.com')
        self.assertEqual(
            self.env['connect.settings']._livekit_api_url(),
            'https://lk.example.com')

    def test_api_url_explicit_wins(self):
        self.settings.sudo().set_param(
            'livekit_api_url', 'https://api.example.com')
        self.assertEqual(
            self.env['connect.settings']._livekit_api_url(),
            'https://api.example.com')

    def test_secret_masked_for_non_manager(self):
        # Write on the actual singleton record: the write() override copies
        # display_* into the real field and masks the display one.
        rec = self.env['connect.settings'].sudo().search([], limit=1)
        rec.write({'display_livekit_api_secret': 'topsecret'})
        self.assertEqual(rec.livekit_api_secret, 'topsecret')
        self.assertEqual(rec.display_livekit_api_secret, '*' * len('topsecret'))

    def test_generate_agent_token(self):
        self.settings.action_generate_livekit_agent_token()
        token = self.settings.sudo().get_param('livekit_agent_token')
        self.assertTrue(token)
        self.assertGreater(len(token), 20)

    def test_create_token_is_jwt(self):
        token = self.env['connect.settings'].livekit_create_token(
            identity='user-1', room_name='meet-abc')
        # JWT: three dot-separated base64url segments.
        self.assertEqual(token.count('.'), 2)

    def test_originate_falls_through_when_not_livekit(self):
        # A user whose originate_provider is not livekit must reach super().
        with patch(
            'odoo.addons.connect.models.settings.Settings.originate_call'
        ) as core_originate:
            with patch.object(
                type(self.env['connect.settings']),
                '_get_originate_provider', return_value='twilio',
            ):
                self.env['connect.settings'].originate_call('+15551234567')
            core_originate.assert_called_once()
