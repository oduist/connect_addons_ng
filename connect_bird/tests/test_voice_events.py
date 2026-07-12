# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import BirdTestCommon


def voice_data(call_id='call-1', status='ringing', direction='inbound',
               from_='+31612345678', to='+15550100', duration=0):
    return {
        'id': call_id,
        'from': from_,
        'to': to,
        'direction': direction,
        'status': status,
        'duration': duration,
    }


@tagged('at_install', '-post_install')
class TestBirdVoiceEvents(BirdTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.connect_user = cls._create_connect_user(
            'bird_agent', bird_phone_number='+15550100')

    def test_inbound_call_chain(self):
        Call = self.env['connect.call']
        for status, duration in (
                ('ringing', 0), ('ongoing', 0), ('completed', 42)):
            Call.on_bird_call_event(
                voice_data(status=status, duration=duration),
                'voice.call.updated')
        channels = self.env['connect.channel'].search(
            [('sid', '=', 'call-1')])
        self.assertEqual(len(channels), 1)
        channel = channels[0]
        self.assertEqual(channel.technical_direction, 'inbound')
        self.assertEqual(channel.status, 'completed')
        self.assertEqual(channel.duration, 42)
        self.assertEqual(channel.called_pbx_user, self.connect_user)
        call = channel.call
        self.assertTrue(call)
        self.assertEqual(call.status, 'completed')
        self.assertEqual(call.direction, 'incoming')
        self.assertEqual(call.duration, 42)
        self.assertEqual(call.bird_call_id, 'call-1')
        self.assertTrue(call.bird_recording_pending)

    def test_status_normalization(self):
        self.env['connect.call'].on_bird_call_event(
            voice_data(call_id='call-cancel', status='cancelled',
                       direction='outbound'),
            'voice.call.updated')
        channel = self.env['connect.channel'].search(
            [('sid', '=', 'call-cancel')])
        self.assertEqual(channel.status, 'canceled')

    def test_status_from_event_suffix(self):
        # No explicit status in data: the event name suffix is used.
        self.env['connect.call'].on_bird_call_event({
            'id': 'call-suffix',
            'from': '+31612345678',
            'to': '+15550100',
            'direction': 'inbound',
        }, 'voice.call.completed')
        channel = self.env['connect.channel'].search(
            [('sid', '=', 'call-suffix')])
        self.assertEqual(channel.status, 'completed')

    def test_failed_call_error_data(self):
        self.env['connect.call'].on_bird_call_event({
            'id': 'call-failed',
            'from': '+31612345678',
            'to': '+15550100',
            'direction': 'inbound',
            'status': 'failed',
            'error': {'code': '486', 'description': 'Busy everywhere'},
        }, 'voice.call.updated')
        channel = self.env['connect.channel'].search(
            [('sid', '=', 'call-failed')])
        call = channel.call
        self.assertTrue(call.has_error)
        self.assertEqual(call.error_code, '486')
        self.assertEqual(call.error_message, 'Busy everywhere')

    def test_events_are_idempotent_on_sid(self):
        data = voice_data(call_id='call-dup', status='ringing')
        self.env['connect.call'].on_bird_call_event(data, 'voice.call.updated')
        self.env['connect.call'].on_bird_call_event(data, 'voice.call.updated')
        self.assertEqual(self.env['connect.channel'].search_count(
            [('sid', '=', 'call-dup')]), 1)
        self.assertEqual(self.env['connect.call'].search_count(
            [('bird_call_id', '=', 'call-dup')]), 1)
