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
