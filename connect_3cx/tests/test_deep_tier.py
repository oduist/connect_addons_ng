# -*- coding: utf-8 -*-
"""Deep tier (ADR-035): participant-event adapter, agent webhooks,
agent-based originate and the journal merge."""
import json
import time
from unittest.mock import patch, MagicMock

from odoo.tests import tagged, HttpCase, new_test_user

from .common import ThreeCXTestCommon, API_KEY, setup_threecx_settings

T0 = 1751900000.0


def participant_event(kind='upsert', dn='101', pid='5', status='Ringing',
                      party='+15551234567', callid=17, legid=2,
                      answered_at=None, ts=None, **state_extra):
    state = {
        'status': status,
        'party_caller_id': party,
        'callid': callid,
        'legid': legid,
    }
    state.update(state_extra)
    return {
        'event': kind,
        'entity': '/callcontrol/{}/participants/{}'.format(dn, pid),
        'dn': dn,
        'participant_id': pid,
        'ts': ts or T0,
        'answered_at': answered_at,
        'state': state,
    }


@tagged('post_install', '-at_install', 'connect_3cx')
class TestThreeCXParticipantAdapter(ThreeCXTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Settings.set_param('threecx_agent_enabled', True)

    def test_inbound_lifecycle(self):
        """Ringing → Connected → remove: completed incoming call with
        the duration measured from the answer stamp."""
        self.Channel.on_threecx_participant_event(participant_event())
        channel = self.Channel.search([('sid', '=', '3cxcc-17-2')])
        self.assertTrue(channel)
        self.assertEqual(channel.status, 'ringing')
        self.assertEqual(channel.technical_direction, 'inbound')
        self.assertEqual(channel.caller_number, '+15551234567')
        self.assertEqual(channel.called_number, '101')
        self.assertEqual(channel.called_pbx_user, self.connect_user)
        self.assertEqual(channel.partner, self.partner)
        self.assertEqual(channel.threecx_callid, '17')
        call = channel.call
        self.assertEqual(call.direction, 'incoming')
        self.assertEqual(call.status, 'ringing')

        self.Channel.on_threecx_participant_event(participant_event(
            status='Connected', answered_at=T0 + 5))
        self.assertEqual(channel.status, 'in-progress')
        self.assertTrue(channel.threecx_answered)

        self.Channel.on_threecx_participant_event(participant_event(
            kind='remove', status='Connected',
            answered_at=T0 + 5, ts=T0 + 47))
        self.assertEqual(channel.status, 'completed')
        self.assertEqual(channel.duration, 42)
        self.assertEqual(call.status, 'completed')
        self.assertEqual(call.duration, 42)

    def test_inbound_missed(self):
        self.Channel.on_threecx_participant_event(participant_event(
            callid=18, legid=1))
        self.Channel.on_threecx_participant_event(participant_event(
            kind='remove', callid=18, legid=1, ts=T0 + 20))
        channel = self.Channel.search([('sid', '=', '3cxcc-18-1')])
        self.assertEqual(channel.status, 'no-answer')
        self.assertEqual(channel.duration, 0)
        self.assertEqual(channel.call.direction, 'incoming')

    def test_outbound_lifecycle(self):
        self.Channel.on_threecx_participant_event(participant_event(
            status='Dialing', party='+15557654321', callid=19, legid=1))
        channel = self.Channel.search([('sid', '=', '3cxcc-19-1')])
        self.assertEqual(channel.technical_direction, 'outbound-api')
        self.assertEqual(channel.caller_number, '101')
        self.assertEqual(channel.called_number, '+15557654321')
        self.assertEqual(channel.caller_pbx_user, self.connect_user)
        self.assertEqual(channel.call.direction, 'outgoing')
        self.Channel.on_threecx_participant_event(participant_event(
            kind='remove', party='+15557654321', callid=19, legid=1,
            answered_at=T0 + 3, ts=T0 + 33))
        self.assertEqual(channel.status, 'completed')
        self.assertEqual(channel.duration, 30)

    def test_originated_by_dn_is_outbound(self):
        self.Channel.on_threecx_participant_event(participant_event(
            status='Ringing', callid=20, legid=1, originated_by_dn='101'))
        channel = self.Channel.search([('sid', '=', '3cxcc-20-1')])
        self.assertEqual(channel.technical_direction, 'outbound-api')

    def test_replay_after_final_ignored(self):
        """A late upsert must not resurrect a finished channel."""
        self.Channel.on_threecx_participant_event(participant_event(
            callid=21, legid=1))
        self.Channel.on_threecx_participant_event(participant_event(
            kind='remove', callid=21, legid=1, ts=T0 + 10))
        channel = self.Channel.search([('sid', '=', '3cxcc-21-1')])
        self.assertEqual(channel.status, 'no-answer')
        self.Channel.on_threecx_participant_event(participant_event(
            callid=21, legid=1))
        self.assertEqual(channel.status, 'no-answer')
        self.assertEqual(
            len(self.Channel.search([('sid', '=', '3cxcc-21-1')])), 1)

    def test_direction_sticky_on_precreated_leg(self):
        """The first WS upsert of an originate-pre-created leg (Ringing
        heuristic says inbound) must not flip its direction."""
        self.Channel.process_channel_event({
            'sid': '3cxcc-22-1',
            'caller': '101',
            'called': '+15557654321',
            'technical_direction': 'outbound-api',
            'status': 'queued',
            'caller_pbx_user_id': self.connect_user.id,
        })
        self.Channel.on_threecx_participant_event(participant_event(
            status='Ringing', party='+15557654321', callid=22, legid=1))
        channel = self.Channel.search([('sid', '=', '3cxcc-22-1')])
        self.assertEqual(len(channel), 1)
        self.assertEqual(channel.technical_direction, 'outbound-api')

    def test_sid_fallback_without_ids(self):
        event = participant_event(callid=None, legid=None)
        event['state'].pop('callid')
        event['state'].pop('legid')
        channel = self.Channel.on_threecx_participant_event(event)
        self.assertTrue(channel.sid.startswith('3cxcc-'))
        self.assertFalse(channel.threecx_callid)

    def test_bad_events_rejected(self):
        self.assertFalse(
            self.Channel.on_threecx_participant_event('garbage'))
        self.assertFalse(
            self.Channel.on_threecx_participant_event({'event': 'dtmf'}))


@tagged('post_install', '-at_install', 'connect_3cx')
class TestThreeCXAgentOriginate(ThreeCXTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Settings.set_param('threecx_agent_enabled', True)

    def _mock_agent(self, payload=None, error=None):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = payload
        response.raise_for_status.return_value = None
        target = ('odoo.addons.connect_3cx.models.settings'
                  '.requests.request')
        if error is not None:
            return patch(target, side_effect=error)
        return patch(target, return_value=response)

    def test_originate_via_agent_precreates_leg(self):
        payload = {'response': {'result': {'callid': 7, 'legid': 3}}}
        with self._mock_agent(payload) as mock:
            result = self.Settings.with_user(
                self.odoo_user).originate_call('+1 555 765-4321')
        self.assertIs(result, True)
        self.assertEqual(mock.call_count, 1)
        self.assertEqual(
            mock.call_args.kwargs['json'],
            {'dn': '101', 'destination': '+15557654321', 'timeout': 30})
        channel = self.Channel.search([('sid', '=', '3cxcc-7-3')])
        self.assertTrue(channel)
        self.assertEqual(channel.status, 'queued')
        self.assertEqual(channel.technical_direction, 'outbound-api')
        self.assertEqual(channel.caller_pbx_user, self.connect_user)
        self.assertEqual(channel.threecx_callid, '7')
        self.assertEqual(channel.call.direction, 'outgoing')

    def test_originate_falls_back_to_dial_url(self):
        with self._mock_agent(error=Exception('agent down')):
            result = self.Settings.with_user(
                self.odoo_user).originate_call('+15557654321')
        self.assertEqual(result['type'], 'ir.actions.act_url')
        self.assertIn('/webclient/#/call?phone=', result['url'])


@tagged('post_install', '-at_install', 'connect_3cx')
class TestThreeCXAgentWebhooks(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        setup_threecx_settings(cls.env)
        cls.Settings = cls.env['connect.settings']
        cls.Settings.set_param('threecx_agent_enabled', True)
        cls.Channel = cls.env['connect.channel']
        cls.odoo_user = new_test_user(
            cls.env, login='tcx_deep_101', groups='base.group_user')
        cls.connect_user = cls.env['connect.user'].with_context(
            no_clear_cache=True).create({
                'user': cls.odoo_user.id,
                'threecx_exten': '101',
            })
        cls.partner = cls.env['res.partner'].with_context(
            no_clear_cache=True).create({
                'name': '3CX Deep Partner',
                'phone': '+15551234567',
            })

    def _post_json(self, path, payload, token=API_KEY):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['X-Connect-Api-Key'] = token
        return self.url_open(path, data=json.dumps(payload),
                             headers=headers)

    def test_config_endpoint(self):
        self.Settings.set_param('threecx_client_id', 'agent-dn')
        self.Settings.set_param('threecx_client_secret', 'agent-secret')
        response = self.url_open(
            '/3cx/api/config',
            headers={'Authorization': 'Bearer %s' % API_KEY})
        self.assertEqual(response.status_code, 200)
        config = response.json()
        self.assertEqual(config['pbx_url'], 'https://pbx.example.com')
        self.assertEqual(config['client_id'], 'agent-dn')
        self.assertEqual(config['client_secret'], 'agent-secret')
        self.assertTrue(config['recordings_enabled'])
        self.assertEqual(
            self.url_open('/3cx/api/config').status_code, 401)

    def test_events_route_dispatches_batch(self):
        events = [
            participant_event(callid=31, legid=1),
            participant_event(kind='remove', callid=31, legid=1,
                              ts=T0 + 15),
            'garbage',
        ]
        response = self._post_json('/3cx/webhook/events', events)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['processed'], 2)
        channel = self.Channel.search([('sid', '=', '3cxcc-31-1')])
        self.assertEqual(channel.status, 'no-answer')

    def test_events_route_requires_agent_toggle(self):
        self.Settings.set_param('threecx_agent_enabled', False)
        try:
            response = self._post_json('/3cx/webhook/events', [])
            self.assertEqual(response.status_code, 401)
        finally:
            self.Settings.set_param('threecx_agent_enabled', True)

    def test_recording_upload_links_channel(self):
        self._post_json('/3cx/webhook/events', [
            participant_event(status='Connected', callid=41, legid=1,
                              answered_at=T0 + 2),
            participant_event(kind='remove', status='Connected',
                              callid=41, legid=1, answered_at=T0 + 2,
                              ts=T0 + 32),
        ])
        channel = self.Channel.search([('sid', '=', '3cxcc-41-1')])
        response = self.url_open(
            '/3cx/webhook/recording/55.wav?callid=41&caller=%2B15551234567',
            data=b'RIFF-fake-audio',
            headers={'X-Connect-Api-Key': API_KEY})
        self.assertEqual(response.status_code, 200)
        recording = self.env['connect.recording'].search(
            [('sid', '=', '55'), ('source', '=', '3cx')])
        self.assertEqual(len(recording), 1)
        self.assertEqual(recording.channel, channel)
        self.assertEqual(recording.call, channel.call)
        self.assertTrue(recording.recording_attachment)
        self.assertEqual(recording.duration, 30)
        # Replays are deduplicated.
        self.url_open(
            '/3cx/webhook/recording/55.wav?callid=41',
            data=b'RIFF-fake-audio',
            headers={'X-Connect-Api-Key': API_KEY})
        self.assertEqual(len(self.env['connect.recording'].search(
            [('sid', '=', '55'), ('source', '=', '3cx')])), 1)

    def test_heartbeat_updates_status(self):
        response = self._post_json('/3cx/webhook/heartbeat', {
            'version': '1.0.0', 'ws_connected': True})
        self.assertEqual(response.status_code, 200)
        self.assertIn('connected',
                      self.Settings.get_param('threecx_agent_status'))
        self.assertEqual(
            self.Settings.get_param('threecx_agent_version'), '1.0.0')

    def test_journal_merges_into_agent_channel(self):
        now_ms = int(time.time() * 1000)
        self._post_json('/3cx/webhook/events', [
            participant_event(status='Connected', callid=51, legid=1,
                              answered_at=T0 + 2),
            participant_event(kind='remove', status='Connected',
                              callid=51, legid=1, answered_at=T0 + 2,
                              ts=T0 + 44),
        ])
        channel = self.Channel.search([('sid', '=', '3cxcc-51-1')])
        self.assertTrue(channel)
        response = self._post_json('/3cx/webhook/report_call', {
            'call_type': 'Inbound',
            'number': '+15551234567',
            'agent': '101',
            'duration': '00:00:42',
            'start_utc_millis': str(now_ms),
            'established_utc_millis': str(now_ms + 2000),
            'end_utc_millis': str(now_ms + 44000),
            'transcription': 'Deep tier transcript.',
            'summary': 'Deep tier summary.',
            'sentiment': 'Neutral',
            'recording_url': 'https://pbx.example.com/rec/51',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get('merged'))
        self.assertEqual(data['sid'], '3cxcc-51-1')
        # No duplicate channel was created for the same call.
        channels = self.Channel.search(
            [('caller_number', '=', '+15551234567'),
             ('called_number', '=', '101')])
        self.assertEqual(len(channels), 1)
        recording = self.env['connect.recording'].search(
            [('channel', '=', channel.id)])
        self.assertEqual(len(recording), 1)
        self.assertEqual(recording.transcript, 'Deep tier transcript.')
        self.assertIn('Deep tier summary.', recording.summary)
        self.assertIn('Deep tier summary.', channel.call.summary)

    def test_journal_falls_back_without_match(self):
        now_ms = int(time.time() * 1000)
        response = self._post_json('/3cx/webhook/report_call', {
            'call_type': 'Inbound',
            'number': '+19995550000',
            'agent': '101',
            'duration': '00:00:10',
            'start_utc_millis': str(now_ms),
            'established_utc_millis': str(now_ms + 1000),
            'end_utc_millis': str(now_ms + 11000),
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertNotIn('merged', data)
        self.assertTrue(data['sid'].startswith('3cx-'))
        self.assertTrue(self.Channel.search([('sid', '=', data['sid'])]))
