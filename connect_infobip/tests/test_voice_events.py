# -*- coding: utf-8 -*-
"""Event-driven voice machine tests: param mapping, inbound routing,
idempotency guards, ring-step advance (ADR-036). All HTTP is mocked."""
from unittest.mock import patch

from odoo.tests import tagged

from .common import InfobipTestCommon, make_response

REQUESTS_PATH = 'odoo.addons.connect_infobip.models.settings.requests.request'


def call_received_event(call_id='call-1', from_='15550002222',
                        to='15550001111', endpoint=None, custom=None):
    call = {
        'id': call_id,
        'direction': 'INBOUND',
        'from': from_,
        'to': to,
        'endpoint': endpoint or {'type': 'PHONE', 'phoneNumber': from_},
    }
    if custom:
        call['customData'] = custom
    return {
        'callId': call_id,
        'timestamp': '2026-07-11T10:00:00.000Z',
        'type': 'CALL_RECEIVED',
        'properties': {'call': call},
    }


def call_status_event(call_id, etype, direction='INBOUND', duration=0,
                      error_name=None, custom=None, timestamp=None):
    call = {
        'id': call_id,
        'direction': direction,
        'duration': duration,
    }
    if custom:
        call['customData'] = custom
    event = {
        'callId': call_id,
        'timestamp': timestamp or '2026-07-11T10:01:00.000Z',
        'type': etype,
        'properties': {'call': call},
    }
    if error_name:
        event['properties']['errorCode'] = {'name': error_name}
    return event


@tagged('at_install', '-post_install')
class TestInfobipVoiceEvents(InfobipTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.connect_user = cls._create_connect_user(
            'ib_voiceuser1', infobip_webrtc_enabled=True,
            infobip_identity='ib-voiceuser1')
        cls.number = cls.env['connect.infobip.number'].with_context(
            skip_infobip_sync=True).create({
                'phone_number': '+15550001111',
                'number_key': 'NK1',
                'capabilities': 'SMS,VOICE',
                'destination': 'user',
                'user': cls.connect_user.id,
            })

    def test_map_inbound_params(self):
        params = self.env['connect.channel']._map_infobip_params(
            call_received_event())
        self.assertEqual(params['sid'], 'call-1')
        self.assertEqual(params['technical_direction'], 'inbound')
        self.assertEqual(params['status'], 'ringing')
        self.assertEqual(params['caller'], '15550002222')
        self.assertEqual(params['to'], '15550001111')
        self.assertNotIn('duration', params)

    def test_map_failed_codes(self):
        event = call_status_event('call-9', 'CALL_FAILED',
                                  error_name='NO_ANSWER')
        params = self.env['connect.channel']._map_infobip_params(event)
        self.assertEqual(params['status'], 'no-answer')
        event = call_status_event('call-9', 'CALL_FAILED', error_name='BUSY')
        params = self.env['connect.channel']._map_infobip_params(event)
        self.assertEqual(params['status'], 'busy')

    def test_map_outbound_custom_data(self):
        event = call_status_event(
            'call-2', 'CALL_RINGING', direction='OUTBOUND',
            custom={'parent_sid': 'call-1', 'technical_direction':
                    'outbound-dial', 'called_pbx_user_id': '7'})
        params = self.env['connect.channel']._map_infobip_params(event)
        self.assertEqual(params['technical_direction'], 'outbound-dial')
        self.assertEqual(params['parent_sid'], 'call-1')
        self.assertEqual(params['called_pbx_user_id'], 7)

    def test_map_ignores_non_status_events(self):
        params = self.env['connect.channel']._map_infobip_params(
            {'callId': 'call-1', 'type': 'SAY_FINISHED'})
        self.assertIsNone(params)

    def test_inbound_call_rings_user(self):
        with patch(REQUESTS_PATH) as mock_request:
            mock_request.return_value = make_response(
                json_data={'id': 'dlg-1', 'childCallId': 'child-1'},
                content=b'{"id": "dlg-1"}')
            self.env['connect.call'].on_infobip_voice_event(
                call_received_event(), 'received')
        channel = self.env['connect.channel'].search(
            [('sid', '=', 'call-1')], limit=1)
        self.assertTrue(channel)
        self.assertTrue(channel.call)
        self.assertEqual(channel.call.direction, 'incoming')
        self.assertEqual(channel.infobip_dialog_id, 'dlg-1')
        self.assertEqual(channel.infobip_route_user, self.connect_user)
        child = self.env['connect.channel'].search(
            [('sid', '=', 'child-1')], limit=1)
        self.assertTrue(child)
        self.assertEqual(child.parent_channel, channel)
        self.assertEqual(child.call, channel.call)
        # The dialog child request dialed the user's WebRTC identity with
        # the platform-side ring timeout.
        args, kwargs = mock_request.call_args
        self.assertIn('/calls/1/dialogs', args[1])
        child_request = kwargs['json']['childCallRequest']
        self.assertEqual(child_request['endpoint']['type'], 'WEBRTC')
        self.assertEqual(
            child_request['endpoint']['identity'], 'ib-voiceuser1')
        self.assertEqual(
            child_request['connectTimeout'],
            self.connect_user.infobip_client_ring_timeout)

    def test_ring_exhausted_says_and_hangs_up(self):
        with patch(REQUESTS_PATH) as mock_request:
            mock_request.return_value = make_response(
                json_data={'id': 'dlg-1', 'childCallId': 'child-1'},
                content=b'{"id": "dlg-1"}')
            self.env['connect.call'].on_infobip_voice_event(
                call_received_event(), 'received')
            # The only ring step fails -> exhausted -> answer the caller
            # to play the apology.
            self.env['connect.call'].on_infobip_voice_event(
                call_status_event(
                    'child-1', 'CALL_FAILED', direction='OUTBOUND',
                    error_name='NO_ANSWER',
                    custom={'parent_sid': 'call-1', 'route_step': '0',
                            'technical_direction': 'outbound-dial'}),
                'event')
        channel = self.env['connect.channel'].search(
            [('sid', '=', 'call-1')], limit=1)
        self.assertEqual(channel.infobip_route_step, 1)
        self.assertTrue(channel.infobip_pending_say)
        called_urls = [c.args[1] for c in mock_request.call_args_list]
        self.assertTrue(any(
            u.endswith('/calls/1/calls/call-1/answer') for u in called_urls))
        # A benign NO_ANSWER never marks the call as errored.
        self.assertFalse(channel.call.has_error)

    def test_terminal_status_not_downgraded(self):
        self.env['connect.call'].on_infobip_voice_event(
            call_status_event('call-5', 'CALL_FINISHED', duration=42),
            'event')
        channel = self.env['connect.channel'].search(
            [('sid', '=', 'call-5')], limit=1)
        self.assertEqual(channel.status, 'completed')
        self.assertEqual(channel.duration, 42)
        # A late RINGING replay must not resurrect the ended leg.
        self.env['connect.call'].on_infobip_voice_event(
            call_status_event('call-5', 'CALL_RINGING',
                              timestamp='2026-07-11T09:59:00.000Z'),
            'event')
        channel = self.env['connect.channel'].search(
            [('sid', '=', 'call-5')], limit=1)
        self.assertEqual(channel.status, 'completed')

    def test_unknown_event_is_ignored(self):
        result = self.env['connect.call'].on_infobip_voice_event(
            {'type': 'SOMETHING_NEW', 'callId': 'call-x'}, 'event')
        self.assertTrue(result)

    def test_webphone_internal_dial_rings_exten_user(self):
        target = self._create_connect_user(
            'ib_voiceuser2', infobip_webrtc_enabled=True,
            infobip_identity='ib-voiceuser2')
        self.env['connect.infobip.exten'].create({
            'number': '8201',
            'model': 'connect.user',
            'res_id': target.id,
        })
        event = call_received_event(
            call_id='app-1', endpoint={'type': 'WEBRTC',
                                       'identity': 'ib-voiceuser1'},
            custom={'dialed_number': '8201'})
        event['properties']['call'].pop('to')
        with patch(REQUESTS_PATH) as mock_request:
            mock_request.return_value = make_response(
                json_data={'id': 'dlg-2', 'childCallId': 'child-2'},
                content=b'{"id": "dlg-2"}')
            self.env['connect.call'].on_infobip_voice_event(event, 'received')
        channel = self.env['connect.channel'].search(
            [('sid', '=', 'app-1')], limit=1)
        self.assertEqual(channel.caller_pbx_user, self.connect_user)
        self.assertEqual(channel.infobip_route_user, target)
        args, kwargs = mock_request.call_args
        child_request = kwargs['json']['childCallRequest']
        self.assertEqual(
            child_request['endpoint']['identity'], 'ib-voiceuser2')
