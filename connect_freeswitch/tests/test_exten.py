# -*- coding: utf-8 -*-
"""connect.freeswitch.exten tests (moved from the shared core exten suite
after the provider model separation, ADR-031)."""
from odoo.tests import tagged

from .common import FsTestCommon


@tagged('at_install', '-post_install')
class TestFsExten(FsTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.connect_user = cls._create_connect_user('fs_extenuser1')
        cls.exten = cls.env['connect.freeswitch.exten'].create({
            'number': '8200',
            'model': 'connect.user',
            'res_id': cls.connect_user.id,
        })

    def test_create_exten(self):
        self.assertTrue(self.exten.id)
        self.assertEqual(self.exten.number, '8200')

    def test_unique_number(self):
        with self.assertRaises(Exception):
            self.env['connect.freeswitch.exten'].create({
                'number': '8200',
                'model': 'connect.user',
                'res_id': self.connect_user.id,
            })

    def test_name_compute(self):
        self.assertIn('8200', self.exten.name)

    def test_model_friendly_compute(self):
        self.assertEqual(self.exten.model_friendly, 'User')

    def test_model_friendly_callflow(self):
        callflow = self.env['connect.freeswitch.callflow'].create({
            'name': 'Test Flow',
        })
        exten = self.env['connect.freeswitch.exten'].create({
            'number': '300',
            'model': 'connect.freeswitch.callflow',
            'res_id': callflow.id,
        })
        self.assertEqual(exten.model_friendly, 'Call Flow')

    def test_dst_compute(self):
        self.assertEqual(self.exten.dst._name, 'connect.user')
        self.assertEqual(self.exten.dst.id, self.connect_user.id)

    def test_dst_without_model(self):
        exten = self.env['connect.freeswitch.exten'].create({
            'number': '999',
        })
        self.assertFalse(exten.dst)
        self.assertFalse(exten.dst_name)

    def test_copy_increments_number(self):
        copy = self.exten.copy()
        self.assertEqual(int(copy.number), int(self.exten.number) + 1)

    def test_user_back_link(self):
        """Creating an exten pointing at a user sets user.freeswitch_exten."""
        self.assertEqual(self.connect_user.freeswitch_exten, self.exten)
        self.assertEqual(self.connect_user.freeswitch_exten_number, '8200')

    def test_unlink_clears_dst_exten(self):
        self.exten.unlink()
        self.assertFalse(self.connect_user.freeswitch_exten)

    def test_create_reuses_orphan_exten(self):
        orphan = self.env['connect.freeswitch.exten'].create({
            'number': '500',
        })
        new_exten = self.env['connect.freeswitch.exten'].create({
            'number': '500',
            'model': 'connect.user',
            'res_id': self.connect_user.id,
        })
        self.assertEqual(orphan.id, new_exten.id)

    def test_create_extension_action(self):
        result = self.env['connect.freeswitch.exten'].create_extension(
            self.connect_user, 'connect.user',
            current_exten=self.connect_user.freeswitch_exten)
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'connect.freeswitch.exten')

    def test_generate_dialplan_no_dst(self):
        exten = self.env['connect.freeswitch.exten'].create({'number': '777'})
        xml = exten.generate_dialplan({})
        self.assertIn('respond', xml)
