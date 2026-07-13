# -*- coding: utf-8 -*-
"""connect.freeswitch.callflow tests (moved from the shared core callflow
suite after the provider model separation, ADR-031)."""
from odoo.tests import tagged
from odoo import Command

from .common import FsTestCommon


@tagged('at_install', '-post_install')
class TestFsCallflow(FsTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.callflow = cls.env['connect.freeswitch.callflow'].create({
            'name': 'Main IVR',
        })

    def test_create_callflow(self):
        self.assertTrue(self.callflow.id)
        self.assertEqual(self.callflow.name, 'Main IVR')

    def test_defaults(self):
        self.assertEqual(self.callflow.language, 'en-US')
        self.assertEqual(self.callflow.gather_input_type, 'dtmf')
        self.assertEqual(self.callflow.gather_timeout, 5)
        self.assertEqual(self.callflow.gather_digits, 1)
        self.assertFalse(self.callflow.gather_input)
        self.assertFalse(self.callflow.record_calls)
        self.assertFalse(self.callflow.voicemail_enabled)

    def test_prompt_message_default(self):
        self.assertIn('Welcome', self.callflow.prompt_message)

    def test_callflow_with_choices(self):
        exten = self.env['connect.freeswitch.exten'].create({'number': '400'})
        self.callflow.write({
            'choices': [
                Command.create({
                    'choice_digits': '1',
                    'exten': exten.id,
                }),
            ],
        })
        self.assertEqual(len(self.callflow.choices), 1)
        self.assertEqual(self.callflow.choices[0].choice_digits, '1')

    def test_callflow_with_ring_users(self):
        user1 = self._create_connect_user('fs_ringuser1')
        user2 = self._create_connect_user('fs_ringuser2')
        self.callflow.write({
            'ring_users': [Command.set([user1.id, user2.id])],
        })
        self.assertEqual(len(self.callflow.ring_users), 2)

    def test_create_extension_action(self):
        result = self.callflow.create_extension()
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'connect.freeswitch.exten')
        self.assertIn('default_dst', result['context'])

    def test_callflow_name_required(self):
        with self.assertRaises(Exception):
            self.env['connect.freeswitch.callflow'].create({})

    def test_generate_dialplan_empty(self):
        """Callflow with no actions responds 404."""
        xml = self.callflow.generate_dialplan({}, exten=None)
        self.assertIn('respond', xml)

    def _enable_voicemail(self, callflow=None):
        self.env['ir.config_parameter'].sudo().set_param(
            'web.base.url', 'https://odoo.test')
        self.env['connect.settings'].sudo().set_param(
            'freeswitch_webhook_token', 'token-token-token-token-token')
        (callflow or self.callflow).write({
            'voicemail_enabled': True,
            'voicemail_prompt': 'Please leave a message.',
        })

    def _create_user_exten(self, login, number):
        user = self._create_connect_user(login)
        exten = self.env['connect.freeswitch.exten'].create({
            'number': number,
            'model': 'connect.user',
            'res_id': user.id,
        })
        user.freeswitch_exten = exten
        user.invalidate_recordset()
        return user

    def test_generate_dialplan_standalone_voicemail(self):
        self._enable_voicemail()

        xml = self.callflow.generate_dialplan({}, exten=None)

        self.assertIn('application="answer"', xml)
        self.assertIn('application="speak"', xml)
        self.assertIn('Please leave a message.', xml)
        self.assertIn('/freeswitch/webhook/voicemail/', xml)
        self.assertIn('application="record"', xml)

    def test_generate_ring_group_voicemail_is_callflow_recording(self):
        user = self._create_user_exten('fs_vm_ringuser', '451')
        self._enable_voicemail()
        self.callflow.write({'ring_users': [Command.set([user.id])]})

        xml = self.callflow.generate_dialplan({}, exten=None)

        self.assertIn('application="bridge"', xml)
        self.assertIn('application="record"', xml)
        self.assertIn('/freeswitch/webhook/voicemail/', xml)
        self.assertNotIn('application="voicemail"', xml)

    def test_generate_ring_group_fifo_precedes_voicemail(self):
        user = self._create_user_exten('fs_vm_fifo_user', '452')
        fifo = self.env['connect.fs_fifo'].create({'name': 'Support'})
        exten = self.env['connect.freeswitch.exten'].create({
            'number': '762',
            'model': 'connect.fs_fifo',
            'res_id': fifo.id,
        })
        fifo.exten = exten
        fifo.invalidate_recordset()
        self._enable_voicemail()
        self.callflow.write({
            'ring_users': [Command.set([user.id])],
            'fs_fifo_id': fifo.id,
        })

        xml = self.callflow.generate_dialplan({}, exten=None)

        self.assertIn('transfer" data="762 XML default"', xml)
        self.assertNotIn('application="record"', xml)

    def test_generate_ivr_timeout_voicemail(self):
        target = self.env['connect.freeswitch.exten'].create({'number': '463'})
        self._enable_voicemail()
        self.callflow.write({
            'gather_input': True,
            'choices': [
                Command.create({
                    'choice_digits': '1',
                    'exten': target.id,
                }),
            ],
        })

        xml = self.callflow.generate_dialplan({}, exten=None)

        self.assertIn('bind_digit_action', xml)
        self.assertIn('application="record"', xml)
        self.assertIn('/freeswitch/webhook/voicemail/', xml)
