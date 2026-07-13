# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.exceptions import ValidationError

from .common import BirdTestCommon, BirdApiMock, patch_bird_request


@tagged('at_install', '-post_install')
class TestBirdOriginate(BirdTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.voice_number = cls._make_number(
            '+15550200', 'voice', is_default=True)
        cls.connect_user = cls._create_connect_user(
            'bird_caller', originate_provider='bird',
            bird_phone_number='+15550100')

    def test_originate_payload_and_ledger(self):
        mock = BirdApiMock(
            default={'id': 'call-orig-1', 'status': 'accepted'})
        with patch_bird_request(mock):
            self.env['connect.settings'].originate_call(
                '+31612345678', user=self.connect_user.user)
        calls = mock.calls_to('POST', '/voice/calls')
        self.assertEqual(len(calls), 1)
        payload = calls[0]['payload']
        self.assertEqual(payload['to'], '+15550100')
        self.assertEqual(payload['from'], '+15550200')
        self.assertEqual(payload['connect_to'], '+31612345678')
        self.assertEqual(payload['record'],
                         self.connect_user.record_calls)
        self.assertTrue(
            payload['notification_url'].endswith('/bird/webhook'))
        channel = self.env['connect.channel'].search(
            [('sid', '=', 'call-orig-1')])
        self.assertEqual(len(channel), 1)
        self.assertEqual(channel.technical_direction, 'outbound-api')
        self.assertEqual(channel.called, '+31612345678')
        self.assertEqual(channel.caller_pbx_user, self.connect_user)
        call = channel.call
        self.assertTrue(call)
        self.assertEqual(call.direction, 'outgoing')
        self.assertEqual(call.called, '+31612345678')

    def test_originate_requires_agent_phone(self):
        self.connect_user.bird_phone_number = False
        mock = BirdApiMock(default={'id': 'x', 'status': 'accepted'})
        with patch_bird_request(mock):
            with self.assertRaises(ValidationError):
                self.env['connect.settings'].originate_call(
                    '+31612345678', user=self.connect_user.user)
        self.assertEqual(mock.calls, [])

    def test_webhook_update_keeps_outbound_api_direction(self):
        mock = BirdApiMock(
            default={'id': 'call-orig-2', 'status': 'accepted'})
        with patch_bird_request(mock):
            self.env['connect.settings'].originate_call(
                '+31612345678', user=self.connect_user.user)
        # Subsequent voice events update the pre-created leg without
        # flipping its technical_direction.
        self.env['connect.call'].on_bird_call_event({
            'id': 'call-orig-2',
            'from': '+15550200',
            'to': '+15550100',
            'direction': 'outbound',
            'status': 'ongoing',
        }, 'voice.call.updated')
        channel = self.env['connect.channel'].search(
            [('sid', '=', 'call-orig-2')])
        self.assertEqual(len(channel), 1)
        self.assertEqual(channel.technical_direction, 'outbound-api')
        self.assertEqual(channel.status, 'in-progress')
