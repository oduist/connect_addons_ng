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
                'record_calls': False,
                'sip_enabled': False,
                'client_enabled': False,
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

    def _mock_client(self, recording_sid='RE123', active_calls=None):
        """Build a Twilio client mock.

        ``active_calls`` maps a call SID to the SID of a recording that is
        already running on that leg; every other leg reports no active
        recording.
        """
        active_calls = active_calls or {}
        created = MagicMock()
        created.sid = recording_sid
        recordings = MagicMock()
        recordings.create.return_value = created
        call_context = MagicMock()
        call_context.recordings = recordings
        client = MagicMock()
        requested = {'sid': None}

        def _calls(call_sid):
            requested['sid'] = call_sid
            return call_context

        def _list(**kwargs):
            running = active_calls.get(requested['sid'])
            if not running:
                return []
            active = MagicMock()
            active.sid = running
            return [active]

        client.calls.side_effect = _calls
        recordings.list.side_effect = _list
        return client, recordings

    def _link_parent(self, child, parent):
        """Attach ``child`` to ``parent`` the way a callflow dial does."""
        child.sudo().write({
            'parent_sid': parent.sid,
            'parent_channel': parent.id,
        })
        return child

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

    def test_recording_state_follows_twilio_not_user_preference(self):
        """The per-user Record Calls flag must not drive the live state."""
        self.connect_user.record_calls = True
        channel = self._channel('CARECDEFAULT')
        client, recordings = self._mock_client()
        with patch.object(type(self.Settings), 'get_client',
                          return_value=client):
            state = self.env['connect.channel'].with_user(
                self.owner_user).get_softphone_recording_state({
                    'provider': 'twilio',
                    'channel_sid': channel.sid,
                })
        self.assertEqual(state['state'], 'off')
        recordings.list.assert_called_with(status='in-progress')

    def test_recording_state_reports_on_for_this_leg(self):
        channel = self._channel('CARECLIVE')
        client, recordings = self._mock_client(
            active_calls={'CARECLIVE': 'RELIVE'})
        with patch.object(type(self.Settings), 'get_client',
                          return_value=client):
            state = self.env['connect.channel'].with_user(
                self.owner_user).get_softphone_recording_state({
                    'provider': 'twilio',
                    'channel_sid': channel.sid,
                })
        self.assertEqual(state['state'], 'on')
        self.assertEqual(state['recording_ref'], 'RELIVE')

    def test_callflow_recording_on_parent_leg_reports_on(self):
        """A callflow records on the leg running <Dial record=...>.

        That is the parent leg, while the softphone holds the client child
        leg, so the child must look up the chain before reporting 'off'.
        """
        parent = self._channel('CAFLOWPARENT')
        child = self._link_parent(self._channel('CAFLOWCHILD'), parent)
        client, recordings = self._mock_client(
            active_calls={'CAFLOWPARENT': 'REFLOW'})
        with patch.object(type(self.Settings), 'get_client',
                          return_value=client):
            state = self.env['connect.channel'].with_user(
                self.owner_user).get_softphone_recording_state({
                    'provider': 'twilio',
                    'channel_sid': child.sid,
                })
        self.assertEqual(state['state'], 'on')
        self.assertEqual(state['recording_ref'], 'REFLOW')

    def test_stop_targets_the_leg_that_carries_the_recording(self):
        parent = self._channel('CASTOPPARENT')
        child = self._link_parent(self._channel('CASTOPCHILD'), parent)
        client, recordings = self._mock_client(
            active_calls={'CASTOPPARENT': 'RESTOPFLOW'})
        with patch.object(type(self.Settings), 'get_client',
                          return_value=client):
            state = self.env['connect.channel'].with_user(
                self.owner_user).stop_softphone_recording({
                    'provider': 'twilio',
                    'channel_sid': child.sid,
                })
        self.assertEqual(state['state'], 'off')
        client.calls.assert_called_with('CASTOPPARENT')
        recordings.assert_called_with('RESTOPFLOW')
        recordings.return_value.update.assert_called_with(status='stopped')

    def test_recording_state_stays_off_when_twilio_is_unreachable(self):
        channel = self._channel('CARECNOAUTO')
        client = MagicMock()
        client.calls.side_effect = Exception('boom')
        with patch.object(type(self.Settings), 'get_client',
                          return_value=client):
            state = self.env['connect.channel'].with_user(
                self.owner_user).get_softphone_recording_state({
                    'provider': 'twilio',
                    'channel_sid': channel.sid,
                })
        self.assertEqual(state['state'], 'off')

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
