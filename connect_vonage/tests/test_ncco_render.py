# -*- coding: utf-8 -*-
"""NCCO rendering tests: NCCO apps, number routing, user callflow engine,
IVR callflows (ADR-036)."""
import json

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import VonageTestCommon, make_channel_event


@tagged('at_install', '-post_install')
class TestNccoRender(VonageTestCommon):

    def test_ncco_static_render(self):
        ncco = self.env['connect.ncco'].create({
            'name': 'Static',
            'ncco': json.dumps([{'action': 'talk', 'text': 'Hi'}]),
        })
        result = ncco.render({})
        self.assertEqual(result, [{'action': 'talk', 'text': 'Hi'}])

    def test_ncco_jinja_render(self):
        ncco = self.env['connect.ncco'].create({
            'name': 'Templated',
            'ncco': '[{"action": "talk", "text": "Hello {{ conversation_uuid }}"}]',
        })
        result = ncco.render({'conversation_uuid': 'conv-42'})
        self.assertEqual(result[0]['text'], 'Hello conv-42')

    def test_ncco_invalid_json(self):
        with self.assertRaises(ValidationError):
            self.env['connect.ncco'].create({
                'name': 'Broken',
                'ncco': '[{"action": "talk" "text": "Hi"}]',
            })

    def test_nccopy_render(self):
        ncco = self.env['connect.ncco'].create({
            'name': 'Python',
            'code_type': 'nccopy',
            'nccopy': "ncco = [{'action': 'talk', 'text': 'From py'}]",
        })
        result = ncco.render({})
        self.assertEqual(result, [{'action': 'talk', 'text': 'From py'}])

    def test_exten_render(self):
        ncco = self.env['connect.ncco'].create({
            'name': 'Exten NCCO',
            'ncco': json.dumps([{'action': 'talk', 'text': 'Ext'}]),
        })
        exten = self.env['connect.exten'].create({'number': '900'})
        exten.dst = ncco
        result = exten.render()
        self.assertEqual(result[0]['text'], 'Ext')

    def test_route_call_unknown_number(self):
        with self.mock_license_check():
            result = self.env['connect.number'].route_call(
                make_channel_event())
        self.assertIn('Number not found', result[0]['text'])

    def test_route_call_to_user(self):
        connect_user = self._create_connect_user('vonage_route_user')
        self.env['connect.number'].create({
            'phone_number': '+15550001111',
            'destination': 'user',
            'user': connect_user.id,
        })
        with self.mock_license_check():
            result = self.env['connect.number'].route_call(
                make_channel_event())
        connect_actions = [a for a in result if a['action'] == 'connect']
        self.assertTrue(connect_actions, result)
        self.assertEqual(
            connect_actions[0]['endpoint'][0],
            {'type': 'app', 'user': connect_user.username})
        self.assertEqual(connect_actions[0]['eventType'], 'synchronous')
        # The inbound channel exists before the NCCO is returned.
        channel = self.env['connect.channel'].search([('sid', '=', 'leg-1')])
        self.assertTrue(channel.call)

    def test_user_callflow_advances_to_voicemail(self):
        """Timeout on the client leg advances the flow to voicemail."""
        connect_user = self._create_connect_user(
            'vonage_vm_user', voicemail_enabled=True)
        self.env['connect.number'].create({
            'phone_number': '+15550001111',
            'destination': 'user',
            'user': connect_user.id,
        })
        with self.mock_license_check():
            first = self.env['connect.number'].route_call(
                make_channel_event())
            self.assertEqual(
                [a['action'] for a in first if a['action'] == 'connect'],
                ['connect'])
            # Synchronous connect event: client leg timed out.
            next_ncco = self.env['connect.user'].on_call_action(
                connect_user.id,
                make_channel_event(
                    uuid='leg-client', conversation_uuid='conv-1',
                    from_='15550001111', to=connect_user.username,
                    status='timeout', direction='outbound'))
        actions = [a['action'] for a in next_ncco]
        self.assertIn('talk', actions)
        self.assertIn('record', actions)
        record = next(a for a in next_ncco if a['action'] == 'record')
        self.assertIn('vm_recording', record['eventUrl'][0])

    def test_on_call_action_continue_on_progress(self):
        connect_user = self._create_connect_user('vonage_cont_user')
        with self.mock_license_check():
            result = self.env['connect.user'].on_call_action(
                connect_user.id,
                make_channel_event(
                    uuid='leg-x', status='answered', direction='outbound'))
        self.assertIsNone(result)

    def test_callflow_gather_render(self):
        callflow = self.env['connect.callflow'].create({
            'name': 'IVR',
            'gather_input': True,
            'gather_digits': 1,
        })
        with self.mock_license_check():
            result = callflow.render(make_channel_event())
        self.assertEqual(result[0]['action'], 'talk')
        self.assertTrue(result[0]['bargeIn'])
        input_action = result[1]
        self.assertEqual(input_action['action'], 'input')
        self.assertEqual(input_action['type'], ['dtmf'])
        self.assertEqual(input_action['dtmf']['maxDigits'], 1)
        self.assertIn(
            'callflow/{}/input'.format(callflow.id),
            input_action['eventUrl'][0])

    def test_callflow_ring_users_sequential(self):
        user1 = self._create_connect_user('vonage_ring1')
        user2 = self._create_connect_user('vonage_ring2')
        callflow = self.env['connect.callflow'].create({
            'name': 'Ring group',
            'ring_users': [(6, 0, [user1.id, user2.id])],
        })
        with self.mock_license_check():
            result = callflow.render(make_channel_event())
        connects = [a for a in result if a['action'] == 'connect']
        self.assertEqual(len(connects), 2)
        users = [a['endpoint'][0]['user'] for a in connects]
        self.assertEqual(set(users), {user1.username, user2.username})

    def test_callflow_gather_action_choice(self):
        ncco = self.env['connect.ncco'].create({
            'name': 'Choice NCCO',
            'ncco': json.dumps([{'action': 'talk', 'text': 'Sales'}]),
        })
        exten = self.env['connect.exten'].create({'number': '901'})
        exten.dst = ncco
        callflow = self.env['connect.callflow'].create({
            'name': 'IVR2',
            'gather_input': True,
            'choices': [(0, 0, {'choice_digits': '1', 'exten': exten.id})],
        })
        with self.mock_license_check():
            result = self.env['connect.callflow'].gather_action(
                callflow.id, {'dtmf': {'digits': '1'}, 'uuid': 'leg-1'})
        self.assertEqual(result[0]['text'], 'Sales')

    def test_callflow_gather_action_invalid(self):
        callflow = self.env['connect.callflow'].create({
            'name': 'IVR3',
            'gather_input': True,
        })
        with self.mock_license_check():
            result = self.env['connect.callflow'].gather_action(
                callflow.id, {'dtmf': {'digits': '9'}, 'uuid': 'leg-1'})
        # Invalid input message followed by the prompt+input again.
        self.assertIn('wrong input', result[0]['text'])
