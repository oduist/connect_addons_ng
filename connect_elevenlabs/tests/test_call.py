# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged('at_install', '-post_install')
class TestElevenlabsCall(TransactionCase):

    def test_inbound_post_call_uses_core_incoming_direction(self):
        call = self.env['connect.call'].create_from_elevenlabs_inbound({
            'conversation_id': 'conv_incoming_direction',
            'metadata': {
                'phone_call': {
                    'external_number': '+15550101010',
                    'agent_number': '+15559990000',
                    'call_sid': 'CAelevenlabsincoming',
                },
                'call_duration_secs': 12,
            },
            'analysis': {
                'call_successful': 'success',
                'transcript_summary': 'A short call.',
            },
        })

        self.assertEqual(call.direction, 'incoming')

    def _post_call_payload(self, conversation_id, dynamic_variables=None,
                           call_sid='CAelevenlabsincoming'):
        payload = {
            'conversation_id': conversation_id,
            'metadata': {
                'phone_call': {
                    # On the SIP-trunk path EL reports the DID as the external
                    # number and its own agent id as the agent number.
                    'external_number': '+15559990000',
                    'agent_number': 'agent_eltest',
                    'call_sid': call_sid,
                },
                'call_duration_secs': 12,
            },
            'analysis': {
                'call_successful': 'success',
                'transcript_summary': 'A short call.',
            },
            'transcript': [{'role': 'user', 'message': 'Hello there'}],
        }
        if dynamic_variables is not None:
            payload['conversation_initiation_client_data'] = {
                'dynamic_variables': dynamic_variables}
        return payload

    def _ledger_call(self):
        """The call the provider already logged for the leg that reached EL."""
        return self.env['connect.call'].create({
            'caller': '101',
            'called': '777',
            'direction': 'outgoing',
            'status': 'completed',
        })

    def test_post_call_attaches_to_the_call_the_provider_logged(self):
        """One phone call is one ledger record.

        render() hands the ledger call id over as X-Connect-Call-Ref and EL
        echoes it back; creating a second record here logged every agent call
        twice.
        """
        existing = self._ledger_call()
        before = self.env['connect.call'].search_count([])

        call = self.env['connect.call'].create_from_elevenlabs_inbound(
            self._post_call_payload('conv_attach', dynamic_variables={
                'sip_connect_call_ref': str(existing.id)}))

        self.assertEqual(call, existing)
        self.assertEqual(self.env['connect.call'].search_count([]), before)
        self.assertEqual(call.elevenlabs_conversation_id, 'conv_attach')
        # The provider's view of the call is authoritative: EL reports the DID
        # as the caller on this path.
        self.assertEqual(call.caller, '101')
        self.assertEqual(call.called, '777')

    def test_post_call_attaches_through_the_channel_sid(self):
        """Without the SIP header, the leg's own CallSid still identifies it."""
        existing = self._ledger_call()
        self.env['connect.channel'].create({
            'sid': 'CAsidattach', 'call': existing.id})
        before = self.env['connect.call'].search_count([])

        call = self.env['connect.call'].create_from_elevenlabs_inbound(
            self._post_call_payload('conv_sid_attach', call_sid='CAsidattach'))

        self.assertEqual(call, existing)
        self.assertEqual(self.env['connect.call'].search_count([]), before)

    def test_native_sip_attach_still_creates_a_call(self):
        """No provider leg, no ledger record -- EL is the only source."""
        before = self.env['connect.call'].search_count([])

        call = self.env['connect.call'].create_from_elevenlabs_inbound(
            self._post_call_payload('conv_native', call_sid='CAnoledgerleg'))

        self.assertEqual(self.env['connect.call'].search_count([]), before + 1)
        self.assertEqual(call.direction, 'incoming')
        self.assertEqual(call.elevenlabs_conversation_id, 'conv_native')

    def test_transcript_lands_on_the_attached_call(self):
        existing = self._ledger_call()

        call = self.env['connect.call'].create_from_elevenlabs_inbound(
            self._post_call_payload('conv_transcript', dynamic_variables={
                'sip_connect_call_ref': str(existing.id)}))

        recording = self.env['connect.recording'].search([('call', '=', call.id)])
        self.assertEqual(len(recording), 1)
        self.assertIn('Hello there', recording.elevenlabs_transcript)

    def test_redelivery_does_not_duplicate(self):
        existing = self._ledger_call()
        payload = self._post_call_payload('conv_redelivered', dynamic_variables={
            'sip_connect_call_ref': str(existing.id)})
        self.env['connect.call'].create_from_elevenlabs_inbound(payload)
        before = self.env['connect.call'].search_count([])

        again = self.env['connect.call'].create_from_elevenlabs_inbound(payload)

        self.assertEqual(again, existing)
        self.assertEqual(self.env['connect.call'].search_count([]), before)
