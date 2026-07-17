from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged, new_test_user


@tagged('at_install', '-post_install')
class TestRecordingControls(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.owner_user = new_test_user(
            cls.env, login='recording_owner',
            groups='base.group_user,connect.group_user')
        cls.other_user = new_test_user(
            cls.env, login='recording_other',
            groups='base.group_user,connect.group_user')
        cls.admin_user = new_test_user(
            cls.env, login='recording_admin',
            groups='base.group_user,connect.group_admin')
        cls.owner_connect_user = cls.env['connect.user'].with_context(
            no_clear_cache=True).create({'user': cls.owner_user.id})

    def _create_call(self, status='in-progress'):
        return self.env['connect.call'].with_context(
            tracking_disable=True).create({
                'caller': '+15551111111',
                'called': '+15552222222',
                'status': status,
                'direction': 'outgoing',
                'caller_user': self.owner_user.id,
            })

    def _create_channel(self, sid='core-rec-1', status='in-progress'):
        return self.env['connect.channel'].with_context(
            tracking_disable=True).create({
                'sid': sid,
                'caller': '+15551111111',
                'called': '+15552222222',
                'status': status,
                'technical_direction': 'outbound-api',
                'caller_user': self.owner_user.id,
                'caller_pbx_user': self.owner_connect_user.id,
                'call': self._create_call(status=status).id,
            })

    def test_unsupported_provider_returns_disabled_state(self):
        channel = self._create_channel()
        result = self.env['connect.channel'].with_user(
            self.owner_user).get_softphone_recording_state({
                'provider': 'telnyx',
                'channel_sid': channel.sid,
            })
        self.assertFalse(result['supported'])
        self.assertEqual(result['state'], 'unsupported')

    def test_owner_can_resolve_own_channel(self):
        channel = self._create_channel('core-rec-owner')
        resolved = self.env['connect.channel'].with_user(
            self.owner_user)._softphone_recording_channel({
                'channel_sid': channel.sid,
            })
        self.assertEqual(resolved.sid, channel.sid)

    def test_admin_can_resolve_any_channel(self):
        channel = self._create_channel('core-rec-admin')
        resolved = self.env['connect.channel'].with_user(
            self.admin_user)._softphone_recording_channel({
                'channel_sid': channel.sid,
            })
        self.assertEqual(resolved.sid, channel.sid)

    def test_other_user_cannot_resolve_channel(self):
        channel = self._create_channel('core-rec-other')
        with self.assertRaises(AccessError):
            self.env['connect.channel'].with_user(
                self.other_user)._softphone_recording_channel({
                    'channel_sid': channel.sid,
                })

    def test_completed_channel_is_not_active(self):
        channel = self._create_channel('core-rec-done', status='completed')
        with self.assertRaises(UserError):
            channel._check_softphone_recording_active()
