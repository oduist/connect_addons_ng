# -*- coding: utf-8 -*-
"""Sequential ring walk of connect.user callflows.

Click-to-call renders the dialplan before the channel exists, so the walk
has to survive a render without a ledger call without ringing the same
device twice.
"""
from odoo.tests import tagged

from .common import TwilioTestCommon


@tagged('at_install', '-post_install')
class TestUserCallflowWalk(TwilioTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['connect.settings'].sudo().set_param(
            'api_url', 'https://pbx.example.com/')
        cls.pbx_user = cls._create_connect_user('walk_user')
        cls.client_flow = cls.env['connect.twilio.user_callflow'].create({
            'user': cls.pbx_user.id,
            'prio': 1,
            'callflow_type': 'client',
            'method': 'render_client',
        })
        cls.sip_flow = cls.env['connect.twilio.user_callflow'].create({
            'user': cls.pbx_user.id,
            'prio': 2,
            'callflow_type': 'sip',
            'method': 'render_sip',
        })

    def test_render_without_call_uses_single_callflow(self):
        """A dialplan built before the channel exists dials one device only."""
        dialplan = self.pbx_user.render()

        self.assertEqual(dialplan.count('<Dial'), 1)
        self.assertIn('<Client', dialplan)
        self.assertNotIn('<Sip', dialplan)

    def test_render_without_call_marks_dialed_callflow(self):
        """The action URL carries the callflow that already rang."""
        dialplan = self.pbx_user.render()

        self.assertIn(
            'done_callflows={}'.format(self.client_flow.id), dialplan)

    def test_action_callback_advances_to_next_callflow(self):
        """An unanswered leg moves on to the next device, not back to the first."""
        dialplan = self.pbx_user.on_call_action(self.pbx_user.id, {
            'CallStatus': 'in-progress',
            'DialCallStatus': 'no-answer',
            'done_callflows': str(self.client_flow.id),
        })

        self.assertIn('<Sip', dialplan)
        self.assertNotIn('<Client', dialplan)
        self.assertIn('done_callflows={},{}'.format(
            self.client_flow.id, self.sip_flow.id), dialplan)

    def test_action_callback_stops_after_last_callflow(self):
        """The walk hangs up once every device has been tried."""
        dialplan = self.pbx_user.on_call_action(self.pbx_user.id, {
            'CallStatus': 'in-progress',
            'DialCallStatus': 'no-answer',
            'done_callflows': '{},{}'.format(
                self.client_flow.id, self.sip_flow.id),
        })

        self.assertIn('<Hangup', dialplan)
        self.assertNotIn('<Dial', dialplan)

    def test_answered_leg_ends_the_call(self):
        """Hanging up an answered leg must not ring the next device."""
        dialplan = self.pbx_user.on_call_action(self.pbx_user.id, {
            'CallStatus': 'in-progress',
            'DialCallStatus': 'completed',
            'done_callflows': str(self.client_flow.id),
        })

        self.assertIn('<Hangup', dialplan)
        self.assertNotIn('<Dial', dialplan)

    def test_caller_hangup_during_ring_ends_the_call(self):
        """A canceled leg means the caller gave up; stop the walk."""
        dialplan = self.pbx_user.on_call_action(self.pbx_user.id, {
            'CallStatus': 'completed',
            'DialCallStatus': 'canceled',
            'done_callflows': str(self.client_flow.id),
        })

        self.assertIn('<Hangup', dialplan)
        self.assertNotIn('<Dial', dialplan)

    def test_dialed_callflows_are_recorded_on_the_ledger(self):
        """Ids carried by the action URL land in the ledger bookkeeping."""
        call = self.env['connect.call'].create({})
        channel = self.env['connect.channel'].create({
            'sid': 'CAwalktest',
            'call': call.id,
        })

        self.pbx_user.on_call_action(self.pbx_user.id, {
            'CallSid': channel.sid,
            'CallStatus': 'in-progress',
            'DialCallStatus': 'no-answer',
            'done_callflows': str(self.client_flow.id),
        })

        done = self.env['connect.twilio.user_callflow_call'].search(
            [('call', '=', call.id)])
        self.assertIn(self.client_flow, done.mapped('callflow'))
