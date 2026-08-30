from odoo.exceptions import ValidationError
from odoo.tests import new_test_user, tagged

from .common import LivekitTestCommon


@tagged('at_install', '-post_install')
class TestLivekitWebPhoneAccess(LivekitTestCommon):
    """The web phone RPCs are reachable by every internal user.

    get_livekit_phone_config is called from JS on every web client load, so
    it must answer neutrally for a user outside the Connect groups rather
    than doing the connect.user lookup. The token/hangup calls have to give
    a definite answer, so those refuse explicitly.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.plain_user = new_test_user(
            cls.env, login='lk_plain', groups='base.group_user')

    def test_phone_config_is_neutral_for_plain_user(self):
        config = self.env['connect.user'].with_user(
            self.plain_user).get_livekit_phone_config()
        self.assertEqual(config, {})

    def test_room_token_refused_for_plain_user(self):
        with self.assertRaises(ValidationError):
            self.env['connect.user'].with_user(
                self.plain_user).get_livekit_room_token('some-room')

    def test_hangup_refused_for_plain_user(self):
        with self.assertRaises(ValidationError):
            self.env['connect.user'].with_user(
                self.plain_user).livekit_hangup_room('some-room')

    def test_phone_config_still_served_to_connect_user(self):
        """The guard must not lock out the users the widget is meant for."""
        self.connect_user.sudo().livekit_client_enabled = True
        config = self.env['connect.user'].with_user(
            self.admin_user).get_livekit_phone_config()
        self.assertTrue(config.get('enabled'))
        self.assertEqual(config.get('ws_url'), 'ws://livekit:7880')
