from odoo.tests import tagged

from .common import LivekitTestCommon


def _participant_event(event, room_name, sid, phone='+15551239999',
                       trunk_phone='+15550000001', kind='SIP'):
    return {
        'event': event,
        'room': {'name': room_name, 'sid': 'RM_1'},
        'participant': {
            'sid': 'PA_' + sid,
            'identity': 'sip_' + sid,
            'kind': kind,
            'attributes': {
                'sip.callID': sid,
                'sip.phoneNumber': phone,
                'sip.trunkPhoneNumber': trunk_phone,
            },
        },
    }


@tagged('at_install', '-post_install')
class TestLivekitLedger(LivekitTestCommon):

    def _dispatch(self, event):
        return self.env['connect.call'].on_livekit_webhook(event)

    def test_foreign_room_ignored(self):
        result = self._dispatch({
            'event': 'participant_joined',
            'room': {'name': 'random-room'},
        })
        self.assertFalse(result)

    def test_inbound_did_creates_channel_and_call(self):
        with self.mock_license_check(True):
            self._dispatch(_participant_event(
                'participant_joined', 'did-1-abcd', 'CALL_1'))
        channel = self.env['connect.channel'].search(
            [('sid', '=', 'CALL_1')])
        self.assertTrue(channel)
        self.assertEqual(channel.technical_direction, 'inbound')
        self.assertEqual(channel.caller, '+15551239999')
        self.assertTrue(channel.call)
        self.assertEqual(channel.call.livekit_room_name, 'did-1-abcd')

    def test_participant_left_completes(self):
        with self.mock_license_check(True):
            self._dispatch(_participant_event(
                'participant_joined', 'did-1-ef01', 'CALL_2'))
            self._dispatch(_participant_event(
                'participant_left', 'did-1-ef01', 'CALL_2'))
        channel = self.env['connect.channel'].search(
            [('sid', '=', 'CALL_2')])
        self.assertEqual(channel.status, 'completed')

    def test_egress_ended_creates_recording(self):
        self.env['connect.call'].create({
            'caller': '+1', 'called': '+2', 'direction': 'incoming',
            'livekit_room_name': 'meet-rec01',
        })
        self._dispatch({
            'event': 'egress_ended',
            'egressInfo': {
                'egressId': 'EG_9',
                'roomName': 'meet-rec01',
                'status': 'EGRESS_COMPLETE',
                'fileResults': [{'filename': '/out/meet-rec01.ogg'}],
            },
        })
        rec = self.env['connect.recording'].search([('sid', '=', 'EG_9')])
        self.assertTrue(rec)
        self.assertEqual(rec.source, 'livekit')
        self.assertEqual(rec.recording_filename, 'meet-rec01.ogg')

    def test_store_recording_file_queues_transcription(self):
        self.settings.sudo().set_param('transcript_calls', True)
        self.settings.sudo().set_param('openai_api_key', 'test-key')
        rec_id = self.env['connect.recording'].livekit_store_recording_file(
            'meet-xyz.ogg', b'YXVkaW8=')
        rec = self.env['connect.recording'].browse(rec_id)
        self.assertEqual(rec.source, 'livekit')
        self.assertTrue(rec.transcription_pending)

    def test_apply_agent_transcript(self):
        call = self.env['connect.call'].create({
            'caller': '+1', 'called': '+2', 'direction': 'incoming',
            'livekit_room_name': 'ai-out-abc',
        })
        agent = self._create_agent()
        rec_id = self.env['connect.call'].livekit_apply_agent_transcript(
            agent, {
                'room_name': 'ai-out-abc',
                'messages': [
                    {'role': 'user', 'text': 'Hi'},
                    {'role': 'assistant', 'text': 'Hello!'},
                ],
                'summary': 'Greeting exchange',
                'duration_secs': 12,
            })
        rec = self.env['connect.recording'].browse(rec_id)
        self.assertEqual(rec.source, 'livekit-ai')
        self.assertIn('user: Hi', rec.transcript)
        self.assertEqual(call.livekit_agent, agent)
        self.assertIn('Greeting exchange', call.summary or '')
        self.assertFalse(rec.transcription_pending)
