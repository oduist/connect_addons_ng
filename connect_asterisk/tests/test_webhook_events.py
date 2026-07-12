# -*- coding: utf-8 -*-
"""AMI event pipeline tests: adapters on connect.channel and the
/asterisk/webhook/events controller (Bearer auth, dispatch)."""
import json
import time

from odoo.tests import tagged, HttpCase

from .common import AsteriskTestCommon, AGENT_TOKEN


@tagged('post_install', '-at_install', 'connect_asterisk')
class TestAmiAdapters(AsteriskTestCommon):

    def test_incoming_call_lifecycle(self):
        """External caller → DID → user endpoint answers → hangup."""
        a_sid, b_sid = 'uid-in-a', 'uid-in-b'
        # A-leg: trunk channel, external caller.
        self.Channel.on_ami_new_channel(self._ami_event(
            'Newchannel', a_sid, channel='PJSIP/trunk-0001',
            caller='+15551234567', exten='101'))
        a_chan = self.Channel.search([('sid', '=', a_sid)])
        self.assertTrue(a_chan)
        self.assertEqual(a_chan.technical_direction, 'inbound')
        self.assertEqual(a_chan.status, 'ringing')
        self.assertFalse(a_chan.caller_pbx_user)
        call = a_chan.call
        self.assertTrue(call)
        self.assertEqual(call.direction, 'incoming')
        self.assertEqual(call.partner, self.partner)
        # B-leg: dialing the user's phone.
        self.Channel.on_ami_new_channel(self._ami_event(
            'Newchannel', b_sid, channel='PJSIP/101-0002',
            caller='+15551234567', exten='s', linkedid=a_sid))
        b_chan = self.Channel.search([('sid', '=', b_sid)])
        self.assertEqual(b_chan.technical_direction, 'outbound-dial')
        self.assertEqual(b_chan.parent_channel, a_chan)
        self.assertEqual(b_chan.call, call)
        self.assertEqual(b_chan.called_pbx_user, self.connect_user)
        # Answer both legs.
        now = time.time()
        self.Channel.on_ami_new_state(self._ami_event(
            'Newstate', b_sid, channel='PJSIP/101-0002', state='Up',
            event_time=now))
        self.Channel.on_ami_new_state(self._ami_event(
            'Newstate', a_sid, channel='PJSIP/trunk-0001', state='Up',
            event_time=now))
        self.assertEqual(a_chan.status, 'in-progress')
        # Hangup both legs after 42 seconds.
        self.Channel.on_ami_hangup(self._ami_event(
            'Hangup', b_sid, channel='PJSIP/101-0002', state='Up',
            Cause='16', event_time=now + 42))
        self.Channel.on_ami_hangup(self._ami_event(
            'Hangup', a_sid, channel='PJSIP/trunk-0001', state='Up',
            Cause='16', event_time=now + 42))
        self.assertEqual(a_chan.status, 'completed')
        self.assertEqual(b_chan.status, 'completed')
        self.assertEqual(call.status, 'completed')
        self.assertEqual(call.duration, 42)
        self.assertEqual(call.answered_pbx_user, self.connect_user)

    def test_internal_call_direction(self):
        """Extension dials another extension → internal call."""
        user2 = self.env['res.users'].create({
            'name': 'User 102', 'login': 'ast_user_102'})
        cu2 = self.env['connect.user'].with_context(
            no_clear_cache=True).create({'user': user2.id})
        self.env['connect.asterisk.endpoint'].create({
            'name': 'Office phone 102',
            'connect_user_id': cu2.id,
            'asterisk_channel': 'PJSIP/102',
        })
        a_sid, b_sid = 'uid-int-a', 'uid-int-b'
        self.Channel.on_ami_new_channel(self._ami_event(
            'Newchannel', a_sid, channel='PJSIP/101-0003',
            caller='101', exten='102'))
        a_chan = self.Channel.search([('sid', '=', a_sid)])
        self.assertEqual(a_chan.caller_pbx_user, self.connect_user)
        self.assertEqual(a_chan.call.direction, 'outgoing')
        self.Channel.on_ami_new_channel(self._ami_event(
            'Newchannel', b_sid, channel='PJSIP/102-0004',
            caller='101', exten='s', linkedid=a_sid))
        b_chan = self.Channel.search([('sid', '=', b_sid)])
        self.assertEqual(b_chan.called_pbx_user, cu2)
        self.assertEqual(b_chan.call.direction, 'internal')

    def test_local_channels_skipped(self):
        result = self.Channel.on_ami_new_channel(self._ami_event(
            'Newchannel', 'uid-local', channel='Local/101@from-queue-0001;2',
            caller='+15551234567', exten='101'))
        self.assertFalse(result)
        self.assertFalse(self.Channel.search([('sid', '=', 'uid-local')]))

    def test_newstate_non_up_ignored(self):
        self.Channel.on_ami_new_channel(self._ami_event(
            'Newchannel', 'uid-ns', caller='+15551234567', exten='101',
            channel='PJSIP/trunk-0005'))
        result = self.Channel.on_ami_new_state(self._ami_event(
            'Newstate', 'uid-ns', state='Ringing',
            channel='PJSIP/trunk-0005'))
        self.assertFalse(result)
        self.assertEqual(
            self.Channel.search([('sid', '=', 'uid-ns')]).status, 'ringing')

    def test_hangup_cause_mapping(self):
        cases = [
            ('17', 'busy'),
            ('19', 'no-answer'),
            ('16', 'canceled'),   # never answered, caller gave up
            ('34', 'failed'),
        ]
        for idx, (cause, expected) in enumerate(cases):
            sid = 'uid-cause-%s' % idx
            self.Channel.on_ami_new_channel(self._ami_event(
                'Newchannel', sid, channel='PJSIP/trunk-%s' % idx,
                caller='+15551234567', exten='101'))
            self.Channel.on_ami_hangup(self._ami_event(
                'Hangup', sid, channel='PJSIP/trunk-%s' % idx,
                state='Ring', Cause=cause))
            channel = self.Channel.search([('sid', '=', sid)])
            self.assertEqual(channel.status, expected,
                             'cause %s must map to %s' % (cause, expected))
            self.assertEqual(channel.duration, 0)

    def test_hangup_unknown_channel_ignored(self):
        result = self.Channel.on_ami_hangup(self._ami_event(
            'Hangup', 'uid-ghost', Cause='16'))
        self.assertFalse(result)

    def test_hangup_replay_is_idempotent(self):
        sid = 'uid-replay'
        self.Channel.on_ami_new_channel(self._ami_event(
            'Newchannel', sid, channel='PJSIP/trunk-0009',
            caller='+15551234567', exten='101'))
        self.Channel.on_ami_hangup(self._ami_event(
            'Hangup', sid, channel='PJSIP/trunk-0009',
            state='Ring', Cause='17'))
        # Reconciler / batch retry replays the hangup with another cause.
        self.Channel.on_ami_hangup(self._ami_event(
            'Hangup', sid, channel='PJSIP/trunk-0009',
            state='Ring', Cause='16'))
        self.assertEqual(
            self.Channel.search([('sid', '=', sid)]).status, 'busy')

    def test_orphan_b_leg_relinked(self):
        """A B-leg arriving before its A-leg is linked when the A-leg comes."""
        a_sid, b_sid = 'uid-orph-a', 'uid-orph-b'
        self.Channel.on_ami_new_channel(self._ami_event(
            'Newchannel', b_sid, channel='PJSIP/101-0006',
            caller='+15551234567', exten='s', linkedid=a_sid))
        b_chan = self.Channel.search([('sid', '=', b_sid)])
        self.assertFalse(b_chan.parent_channel)
        orphan_call = b_chan.call
        self.Channel.on_ami_new_channel(self._ami_event(
            'Newchannel', a_sid, channel='PJSIP/trunk-0007',
            caller='+15551234567', exten='101'))
        a_chan = self.Channel.search([('sid', '=', a_sid)])
        self.assertEqual(b_chan.parent_channel, a_chan)
        self.assertEqual(b_chan.call, a_chan.call)
        if orphan_call and orphan_call != a_chan.call:
            self.assertFalse(orphan_call.exists())

    def test_var_set_records_filename(self):
        sid = 'uid-rec'
        self.Channel.on_ami_new_channel(self._ami_event(
            'Newchannel', sid, channel='PJSIP/trunk-0008',
            caller='+15551234567', exten='101'))
        self.Channel.on_ami_var_set(self._ami_event(
            'VarSet', sid, channel='PJSIP/trunk-0008',
            Variable='MIXMONITOR_FILENAME',
            Value='/var/spool/asterisk/monitor/uid-rec.wav'))
        self.assertEqual(
            self.Channel.search([('sid', '=', sid)]).asterisk_recording_file,
            '/var/spool/asterisk/monitor/uid-rec.wav')
        # Other variables are ignored.
        self.assertFalse(self.Channel.on_ami_var_set(self._ami_event(
            'VarSet', sid, Variable='OTHER', Value='x')))


@tagged('post_install', '-at_install', 'connect_asterisk')
class TestEventsWebhook(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['connect.settings'].set_param(
            'asterisk_agent_token', AGENT_TOKEN)

    def _post_events(self, payload, token=AGENT_TOKEN):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer %s' % token
        return self.url_open(
            '/asterisk/webhook/events', data=json.dumps(payload),
            headers=headers)

    def test_events_requires_token(self):
        response = self._post_events([], token=None)
        self.assertEqual(response.status_code, 401)
        response = self._post_events([], token='wrong-token')
        self.assertEqual(response.status_code, 401)

    def test_events_batch_processed(self):
        events = [
            {'Event': 'Newchannel', 'Uniqueid': 'uid-http-1',
             'Linkedid': 'uid-http-1', 'Channel': 'PJSIP/trunk-1000',
             'CallerIDNum': '+15550001111', 'Exten': '101',
             'ChannelStateDesc': 'Ring', 'EventTime': time.time()},
            {'Event': 'UnknownEvent', 'Uniqueid': 'x'},
        ]
        response = self._post_events(events)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['processed'], 1)
        channel = self.env['connect.channel'].search(
            [('sid', '=', 'uid-http-1')])
        self.assertTrue(channel)
        self.assertEqual(channel.status, 'ringing')

    def test_events_bad_json(self):
        response = self.url_open(
            '/asterisk/webhook/events', data='{not json',
            headers={'Content-Type': 'application/json',
                     'Authorization': 'Bearer %s' % AGENT_TOKEN})
        self.assertEqual(response.status_code, 400)
