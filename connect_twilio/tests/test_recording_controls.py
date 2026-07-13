# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged, new_test_user


@tagged('at_install', '-post_install')
class TestTwilioRecordingControls(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.owner_user = new_test_user(
            cls.env, login='tw_rec_owner',
            groups='base.group_user,connect.group_user')
        cls.other_user = new_test_user(
            cls.env, login='tw_rec_other',
            groups='base.group_user,connect.group_user')
        cls.connect_user = cls.env['connect.user'].with_context(
            no_clear_cache=True, no_twilio_create=True).create({
                'user': cls.owner_user.id,
            })
        cls.Settings = cls.env['connect.settings']
        cls.Settings.set_param('api_url', 'https://odoo.example.com/')
        cls.Settings.set_param('twilio_edge', 'ashburn')

    def _channel(self, sid='CAREC1', status='in-progress'):
        call = self.env['connect.call'].with_context(
            tracking_disable=True).create({
                'caller': '+15551111111',
                'called': '+15552222222',
                'status': status,
                'direction': 'outgoing',
                'caller_user': self.owner_user.id,
            })
        return self.env['connect.channel'].with_context(
            tracking_disable=True).create({
                'sid': sid,
                'caller': '+15551111111',
                'called': '+15552222222',
                'status': status,
                'technical_direction': 'outbound-api',
                'caller_user': self.owner_user.id,
                'caller_pbx_user': self.connect_user.id,
                'call': call.id,
            })

    def _mock_client(self, recording_sid='RE123'):
        recording = MagicMock()
        recording.sid = recording_sid
        recordings = MagicMock()
        recordings.create.return_value = recording
        call_context = MagicMock()
        call_context.recordings = recordings
        client = MagicMock()
        client.calls.return_value = call_context
        return client, recordings

    def test_start_recording_creates_twilio_recording(self):
        channel = self._channel()
        client, recordings = self._mock_client()
        with patch.object(type(self.Settings), 'get_client',
                          return_value=client):
            result = self.env['connect.channel'].with_user(
                self.owner_user).start_softphone_recording({
                    'provider': 'twilio',
                    'channel_sid': channel.sid,
                })
        self.assertEqual(result['state'], 'on')
        self.assertEqual(channel.sudo().recording_control_ref, 'RE123')
        client.calls.assert_called_with(channel.sid)
        self.assertEqual(recordings.create.call_args.kwargs[
            'recording_channels'], 'dual')

    def test_stop_recording_uses_current_when_no_ref(self):
        channel = self._channel('CAREC2')
        client, recordings = self._mock_client()
        with patch.object(type(self.Settings), 'get_client',
                          return_value=client):
            result = self.env['connect.channel'].with_user(
                self.owner_user).stop_softphone_recording({
                    'provider': 'twilio',
                    'channel_sid': channel.sid,
                })
        self.assertEqual(result['state'], 'off')
        recordings.assert_called_with('Twilio.CURRENT')
        recordings.return_value.update.assert_called_with(status='stopped')

    def test_stop_recording_uses_stored_ref(self):
        channel = self._channel('CAREC3')
        channel.sudo().recording_control_ref = 'REABC'
        client, recordings = self._mock_client()
        with patch.object(type(self.Settings), 'get_client',
                          return_value=client):
            self.env['connect.channel'].with_user(
                self.owner_user).stop_softphone_recording({
                    'provider': 'twilio',
                    'channel_sid': channel.sid,
                })
        recordings.assert_called_with('REABC')

    def test_default_recording_state_infers_on_until_stopped(self):
        self.connect_user.record_calls = True
        channel = self._channel('CARECDEFAULT')
        state = self.env['connect.channel'].with_user(
            self.owner_user).get_softphone_recording_state({
                'provider': 'twilio',
                'channel_sid': channel.sid,
            })
        self.assertEqual(state['state'], 'on')

        client, recordings = self._mock_client()
        with patch.object(type(self.Settings), 'get_client',
                          return_value=client):
            state = self.env['connect.channel'].with_user(
                self.owner_user).stop_softphone_recording({
                    'provider': 'twilio',
                    'channel_sid': channel.sid,
                })
        self.assertEqual(state['state'], 'off')
        self.assertEqual(channel.sudo().recording_control_ref, 'manual-off')
        recordings.assert_called_with('Twilio.CURRENT')

    def test_other_user_cannot_control_recording(self):
        channel = self._channel('CAREC4')
        with self.assertRaises(AccessError):
            self.env['connect.channel'].with_user(
                self.other_user).start_softphone_recording({
                    'provider': 'twilio',
                    'channel_sid': channel.sid,
                })

    def test_completed_call_cannot_start_recording(self):
        channel = self._channel('CAREC5', status='completed')
        with self.assertRaises(UserError):
            self.env['connect.channel'].with_user(
                self.owner_user).start_softphone_recording({
                    'provider': 'twilio',
                    'channel_sid': channel.sid,
                })
