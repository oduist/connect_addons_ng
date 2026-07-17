# -*- coding: utf-8 -*-
"""Voice event mapping and channel/call machine tests (ADR-036)."""
from odoo.tests import tagged

from .common import VonageTestCommon, make_channel_event


@tagged('at_install', '-post_install')
class TestVonageVoiceEvents(VonageTestCommon):

    def test_map_inbound_params(self):
        params = self.env['connect.channel']._map_vonage_params(
            make_channel_event())
        self.assertEqual(params['sid'], 'leg-1')
        self.assertEqual(params['technical_direction'], 'inbound')
        self.assertEqual(params['status'], 'initiated')
        self.assertEqual(params['caller'], '+15550002222')
        self.assertEqual(params['called'], '+15550001111')

    def test_map_status_vocabulary(self):
        cases = {
            'started': 'initiated',
            'ringing': 'ringing',
            'answered': 'in-progress',
            'completed': 'completed',
            'busy': 'busy',
            'cancelled': 'canceled',
            'timeout': 'no-answer',
            'unanswered': 'no-answer',
            'rejected': 'failed',
            'failed': 'failed',
        }
        for vonage_status, core_status in cases.items():
            params = self.env['connect.channel']._map_vonage_params(
                make_channel_event(status=vonage_status))
            self.assertEqual(params['status'], core_status,
                             'status {}'.format(vonage_status))

    def test_map_app_leg_to_client_uri(self):
        params = self.env['connect.channel']._map_vonage_params(
            make_channel_event(from_='alice', to='15550001111'))
        self.assertEqual(params['caller'], 'client:alice@vonage')
        params = self.env['connect.channel']._map_vonage_params(
            make_channel_event(to={'type': 'app', 'user': 'bob'}))
        self.assertEqual(params['called'], 'client:bob@vonage')

    def test_map_ignores_non_status_events(self):
        params = self.env['connect.channel']._map_vonage_params(
            {'conversation_uuid': 'conv-1', 'reason': 'Syntax error in NCCO'})
        self.assertIsNone(params)

    def test_inbound_call_creates_channel_and_call(self):
        with self.mock_license_check():
            self.env['connect.call'].on_voice_event(make_channel_event())
        channel = self.env['connect.channel'].search(
            [('sid', '=', 'leg-1')], limit=1)
        self.assertTrue(channel)
        self.assertEqual(channel.conversation_uuid, 'conv-1')
        self.assertTrue(channel.call)
        self.assertEqual(channel.call.direction, 'incoming')
        self.assertEqual(channel.partner, self.partner)

    def test_parent_resolution_by_conversation_uuid(self):
        with self.mock_license_check():
            self.env['connect.call'].on_voice_event(
                make_channel_event(uuid='leg-a', conversation_uuid='conv-p'))
            self.env['connect.call'].on_voice_event(
                make_channel_event(
                    uuid='leg-b', conversation_uuid='conv-p',
                    from_='15550001111', to='bob', direction='outbound',
                    status='ringing'))
        leg_a = self.env['connect.channel'].search([('sid', '=', 'leg-a')])
        leg_b = self.env['connect.channel'].search([('sid', '=', 'leg-b')])
        self.assertEqual(leg_b.parent_sid, 'leg-a')
        self.assertEqual(leg_b.parent_channel, leg_a)
        self.assertEqual(leg_b.call, leg_a.call)
        self.assertEqual(leg_b.technical_direction, 'outbound-dial')

    def test_precreated_direction_preserved(self):
        """Sparse events must not wipe values set at originate time."""
        self.env['connect.channel'].sudo().create({
            'sid': 'leg-orig',
            'conversation_uuid': 'conv-o',
            'technical_direction': 'outbound-api',
            'caller': '+15550001111',
            'called': '+15559998888',
        })
        with self.mock_license_check():
            self.env['connect.call'].on_voice_event(make_channel_event(
                uuid='leg-orig', conversation_uuid='conv-o',
                from_='', to='', status='answered', direction='inbound'))
        channel = self.env['connect.channel'].search(
            [('sid', '=', 'leg-orig')])
        self.assertEqual(channel.technical_direction, 'outbound-api')
        self.assertEqual(channel.caller, '+15550001111')
        self.assertEqual(channel.called, '+15559998888')
        self.assertEqual(channel.status, 'in-progress')

    def test_call_completion(self):
        with self.mock_license_check():
            self.env['connect.call'].on_voice_event(make_channel_event())
            self.env['connect.call'].on_voice_event(make_channel_event(
                status='completed', duration='42'))
        channel = self.env['connect.channel'].search([('sid', '=', 'leg-1')])
        self.assertEqual(channel.call.status, 'completed')
        self.assertEqual(channel.call.duration, 42)

    def test_error_data_on_failed_call(self):
        with self.mock_license_check():
            self.env['connect.call'].on_voice_event(make_channel_event())
            self.env['connect.call'].on_voice_event(make_channel_event(
                status='failed', reason='Carrier error'))
        channel = self.env['connect.channel'].search([('sid', '=', 'leg-1')])
        self.assertTrue(channel.call.has_error)
        self.assertEqual(channel.call.error_message, 'Carrier error')
