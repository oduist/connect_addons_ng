# -*- coding: utf-8 -*-
"""connect.twilio.callflow tests (moved from the shared core callflow
suite after the provider model separation, ADR-031)."""
from odoo.tests import tagged
from odoo import Command

from .common import TwilioTestCommon


@tagged('at_install', '-post_install')
class TestTwilioCallflow(TwilioTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.callflow = cls.env['connect.twilio.callflow'].create({
            'name': 'Main IVR',
        })

    def test_create_callflow(self):
        self.assertTrue(self.callflow.id)

    def test_defaults(self):
        self.assertEqual(self.callflow.language, 'en-US')
        self.assertEqual(self.callflow.voice, 'Woman')
        self.assertEqual(self.callflow.gather_input_type, 'dtmf')
        self.assertEqual(self.callflow.gather_timeout, 5)
        self.assertEqual(self.callflow.gather_digits, 1)

    def test_gather_input_type_speech_available(self):
        """Twilio callflow natively offers the speech gather modes."""
        keys = [k for k, _ in self.callflow._fields['gather_input_type'].selection]
        self.assertIn('speech', keys)
        self.assertIn('dtmf speech', keys)

    def test_callflow_with_choices(self):
        exten = self.env['connect.twilio.exten'].create({'number': '400'})
        self.callflow.write({
            'choices': [
                Command.create({
                    'choice_digits': '1',
                    'exten': exten.id,
                    'speech': 'sales',
                }),
            ],
        })
        self.assertEqual(len(self.callflow.choices), 1)
        self.assertEqual(self.callflow.choices[0].speech, 'sales')

    def test_callflow_with_ring_users(self):
        user1 = self._create_connect_user('tw_ringuser1')
        self.callflow.write({'ring_users': [Command.set([user1.id])]})
        self.assertEqual(len(self.callflow.ring_users), 1)

    def test_ring_group_voicemail_requires_enabled(self):
        self.callflow.write({
            'voicemail_enabled': False,
            'voicemail_prompt': 'Leave a message.',
        })

        response = self.callflow.on_call_action(
            self.callflow.id, {'DialCallStatus': 'no-answer'})

        self.assertNotIn('<Record', str(response))
        self.assertIn('Sorry, I could not connect your call', str(response))

    def test_ring_group_voicemail_enabled_records(self):
        self.env['connect.settings'].set_param('api_url', 'https://odoo.test/')
        self.callflow.write({
            'voicemail_enabled': True,
            'voicemail_prompt': 'Leave a message.',
        })

        response = self.callflow.on_call_action(
            self.callflow.id, {'DialCallStatus': 'no-answer'})

        self.assertIn('<Record', str(response))
        self.assertIn('Leave a message.', str(response))

    def test_create_extension_action(self):
        result = self.callflow.create_extension()
        self.assertEqual(result['res_model'], 'connect.twilio.exten')

    def test_callflow_name_required(self):
        with self.assertRaises(Exception):
            self.env['connect.twilio.callflow'].create({})
