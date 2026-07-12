# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged, new_test_user


@tagged('at_install', '-post_install')
class TestFreeSwitchRecordingControls(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.owner_user = new_test_user(
            cls.env, login='fs_rec_owner',
            groups='base.group_user,connect.group_user')
        cls.other_user = new_test_user(
            cls.env, login='fs_rec_other',
            groups='base.group_user,connect.group_user')
        cls.connect_user = cls.env['connect.user'].with_context(
            no_clear_cache=True).create({
                'user': cls.owner_user.id,
                'record_calls': False,
            })
        cls.Settings = cls.env['connect.settings']
        cls.Settings.set_param('freeswitch_webhook_token', 'fs-token-1234567890')
        cls.env['ir.config_parameter'].sudo().set_param(
            'web.base.url', 'https://odoo.example.com')

    def _api_side_effect(self, command, args=''):
        if command == 'uuid_getvar':
            if args == 'uuid-1 odoo_user_id':
                return str(self.owner_user.id)
            if args == 'uuid-1 odoo_connect_user_id':
                return str(self.connect_user.id)
            if args == 'uuid-1 odoo_recording_path':
                return ''
            if args == 'uuid-1 odoo_recording_state':
                return ''
            return ''
        return '+OK'

    def test_start_recording_calls_uuid_record(self):
        calls = []

        def fake_api(command, args=''):
            calls.append((command, args))
            return self._api_side_effect(command, args)

        with patch.object(type(self.Settings), 'freeswitch_api',
                          side_effect=fake_api):
            result = self.env['connect.channel'].with_user(
                self.owner_user).start_softphone_recording({
                    'provider': 'freeswitch',
                    'call_id': 'uuid-1',
                })
        self.assertEqual(result['state'], 'on')
        record_calls = [args for command, args in calls
                        if command == 'uuid_record']
        self.assertEqual(len(record_calls), 1)
        self.assertTrue(record_calls[0].startswith('uuid-1 start '))
        self.assertIn('/uuid-1__', record_calls[0])

    def test_stop_recording_uses_default_path_when_no_segment_path(self):
        calls = []

        def fake_api(command, args=''):
            calls.append((command, args))
            return self._api_side_effect(command, args)

        self.connect_user.record_calls = True
        with patch.object(type(self.Settings), 'freeswitch_api',
                          side_effect=fake_api):
            result = self.env['connect.channel'].with_user(
                self.owner_user).stop_softphone_recording({
                    'provider': 'freeswitch',
                    'call_id': 'uuid-1',
                })
        self.assertEqual(result['state'], 'off')
        record_calls = [args for command, args in calls
                        if command == 'uuid_record']
        self.assertEqual(record_calls, [
            'uuid-1 stop https://odoo.example.com/freeswitch/webhook/'
            'recording/fs-token-1234567890/uuid-1.wav'
        ])

    def test_other_user_cannot_control_uuid(self):
        with patch.object(type(self.Settings), 'freeswitch_api',
                          side_effect=self._api_side_effect):
            with self.assertRaises(AccessError):
                self.env['connect.channel'].with_user(
                    self.other_user).start_softphone_recording({
                        'provider': 'freeswitch',
                        'call_id': 'uuid-1',
                    })
