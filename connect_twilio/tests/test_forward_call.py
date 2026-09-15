# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged, new_test_user


@tagged('at_install', '-post_install')
class TestTwilioForwardCall(TransactionCase):
    """Blind transfer from the softphone (ADR-064).

    The behaviour worth pinning down is which leg moves and that routing is
    not reimplemented: the other party is redirected back at the same TwiML
    application that routes every outgoing call, with the destination carried
    in `forward_to`.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.owner_user = new_test_user(
            cls.env, login='tw_fwd_owner',
            groups='base.group_user,connect.group_user')
        cls.other_user = new_test_user(
            cls.env, login='tw_fwd_other',
            groups='base.group_user,connect.group_user')
        cls.Settings = cls.env['connect.settings']
        cls.Settings.set_param('api_url', 'https://odoo.example.com/')
        cls.Settings.set_param('twilio_edge', 'ashburn')

        cls.application = cls.env['connect.twilio.twiml'].with_context(
            install_mode=True).create({
                'name': 'Routing App', 'sid': 'AP' + '9' * 32,
                'code_type': 'twiml', 'twiml': '<Response/>',
            })
        cls.domain = cls.env['connect.twilio.domain'].with_context(
            no_twilio_create=True).create({
                'sid': 'SD' + '9' * 32, 'subdomain': 'fwd',
                'domain_name': 'fwd.sip.twilio.com', 'friendly_name': 'Fwd',
                'application': cls.application.id,
            })
        cls.connect_user = cls.env['connect.user'].with_context(
            no_clear_cache=True, no_twilio_create=True).create({
                'user': cls.owner_user.id,
                'username': 'fwdowner',
                'domain': cls.domain.id,
                'sip_enabled': False,
                'client_enabled': False,
            })

    def _live_call(self, other_status='in-progress'):
        """A two-legged call: the softphone's own leg plus the other party."""
        call = self.env['connect.call'].with_context(
            tracking_disable=True).create({
                'caller': '101', 'called': '+15552222222',
                'status': 'in-progress', 'direction': 'outgoing',
                'caller_user': self.owner_user.id,
            })
        mine = self.env['connect.channel'].with_context(
            tracking_disable=True).create({
                'sid': 'CAMINE', 'call': call.id, 'status': 'in-progress',
                'technical_direction': 'inbound',
                'caller_pbx_user': self.connect_user.id,
            })
        self.env['connect.channel'].with_context(
            tracking_disable=True).create({
                'sid': 'CAOTHER', 'call': call.id, 'status': other_status,
                'technical_direction': 'outbound-dial',
            })
        return mine

    def _mock_client(self, captured, parent_sid=None, children=()):
        """Twilio stand-in.

        `parent_sid` / `children` drive the fallback path: what Twilio would
        say about our leg when the ledger cannot name a single sibling.
        """
        class _Calls:
            def __init__(self, sid):
                captured['sid'] = sid

            def update(self, **kwargs):
                captured.update(kwargs)
                return MagicMock()

            def fetch(self):
                leg = MagicMock()
                leg.parent_call_sid = parent_sid
                return leg

        client = MagicMock()
        client.calls.side_effect = _Calls
        client.calls.list.return_value = list(children)
        return client

    def _child(self, sid, status='in-progress'):
        child = MagicMock()
        child.sid = sid
        child.status = status
        return child

    def _forward(self, captured, user=None, number='100', sid='CAMINE',
                 parent_sid=None, children=()):
        client = self._mock_client(captured, parent_sid, children)
        with patch.object(type(self.Settings), 'get_client', return_value=client):
            return self.env['connect.channel'].with_user(
                user or self.owner_user).forward_softphone_call({
                    'provider': 'twilio', 'channel_sid': sid, 'number': number,
                })

    # ------------------------------------------------------------------

    def test_redirects_the_other_leg_not_our_own(self):
        """The party who should end up talking to the target is the one moved."""
        self._live_call()
        captured = {}
        result = self._forward(captured)

        self.assertEqual(captured['sid'], 'CAOTHER')
        self.assertEqual(result['channel_sid'], 'CAOTHER')
        self.assertEqual(result['forwarded_to'], '100')

    def test_redirects_to_the_routing_application(self):
        """Routing is reused, so the redirect points back at the TwiML app."""
        self._live_call()
        captured = {}
        self._forward(captured)

        twiml = captured['twiml']
        self.assertIn('<Redirect', twiml)
        self.assertIn('/twilio/webhook/twiml/', twiml)
        self.assertIn('forward_to=100', twiml)

    def test_announces_before_moving_the_caller(self):
        """Being redirected with no warning reads as a dropped call."""
        self._live_call()
        captured = {}
        self._forward(captured)

        twiml = captured['twiml']
        self.assertIn('Transferring your call now.', twiml)
        self.assertLess(
            twiml.index('Transferring'), twiml.index('<Redirect'),
            'the announcement has to play before the redirect')

    def test_query_precedes_the_url_fragment(self):
        """Voice URLs end in `#e=<edge>`.

        A query appended after the fragment would be swallowed by it and
        Twilio would never send `forward_to`.
        """
        self._live_call()
        captured = {}
        self._forward(captured)

        twiml = captured['twiml']
        self.assertLess(
            twiml.index('forward_to'), twiml.index('#e='),
            'forward_to must precede the fragment, got %s' % twiml)

    def test_external_number_keeps_its_plus(self):
        """E.164 has to survive, or the destination stops looking external."""
        self._live_call()
        captured = {}
        self._forward(captured, number='+15559998888')

        self.assertIn('forward_to=%2B15559998888', captured['twiml'])

    def test_refuses_an_empty_number(self):
        self._live_call()
        with self.assertRaises(UserError):
            self._forward({}, number='   ')

    def test_refuses_when_nobody_else_is_on_the_line(self):
        """Nothing to hand over once the other leg has gone."""
        self._live_call(other_status='completed')
        with self.assertRaises(UserError):
            self._forward({})

    # -- falling back to Twilio when the ledger cannot answer ----------

    def test_falls_back_to_the_twilio_parent(self):
        """An inbound leg: we are the child, so the parent is the customer.

        The ledger is short a sibling here -- a channel row still in flight is
        the everyday cause -- and refusing would block a transfer the user can
        see is possible.
        """
        self._live_call(other_status='completed')
        captured = {}
        result = self._forward(captured, parent_sid='CAPARENT')

        self.assertEqual(captured['sid'], 'CAPARENT')
        self.assertEqual(result['channel_sid'], 'CAPARENT')

    def test_falls_back_to_the_twilio_child(self):
        """An outbound leg: we are the parent, so the callee is our child."""
        self._live_call(other_status='completed')
        captured = {}
        result = self._forward(
            captured, children=[self._child('CACHILD')])

        self.assertEqual(captured['sid'], 'CACHILD')
        self.assertEqual(result['channel_sid'], 'CACHILD')

    def test_fallback_ignores_finished_children(self):
        """A leg that has already hung up is not the party to forward."""
        self._live_call(other_status='completed')
        with self.assertRaises(UserError):
            self._forward(
                {}, children=[self._child('CADEAD', status='completed')])

    def test_ledger_answer_costs_no_api_call(self):
        """The common case must not add a round-trip to a live call."""
        self._live_call()
        captured = {}
        client = self._mock_client(captured)
        with patch.object(type(self.Settings), 'get_client', return_value=client):
            self.env['connect.channel'].with_user(
                self.owner_user).forward_softphone_call({
                    'provider': 'twilio', 'channel_sid': 'CAMINE',
                    'number': '100'})

        client.calls.list.assert_not_called()

    def test_refuses_a_call_that_is_not_ours(self):
        self._live_call()
        with self.assertRaises(AccessError):
            self._forward({}, user=self.other_user)

    def test_refuses_an_unknown_provider(self):
        self._live_call()
        with self.assertRaises(UserError):
            self.env['connect.channel'].with_user(
                self.owner_user).forward_softphone_call({
                    'provider': 'nosuchprovider',
                    'channel_sid': 'CAMINE', 'number': '100',
                })

    def test_route_call_prefers_forward_to_over_the_original_destination(self):
        """A forwarded leg routes to the target, not to where it was going."""
        exten = self.env['connect.twilio.exten'].with_context(
            no_twilio_create=True).create({'number': '778'})
        self.assertTrue(exten)
        with patch.object(
                type(self.env['connect.call']), 'on_call_status',
                return_value=None):
            rendered = str(self.env['connect.twilio.domain'].route_call(
                {'To': '+15552222222', 'From': 'client:x', 'forward_to': '778'}))
        # Routed by the extension, i.e. the original To was ignored.
        self.assertNotIn('+15552222222', rendered)
