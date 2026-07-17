# -*- coding: utf-8 -*-
"""connect.infobip.exten tests (dst-Reference mechanics copied per
ADR-031/ADR-036; v1 routes to users only)."""
from odoo.tests import tagged

from .common import InfobipTestCommon


@tagged('at_install', '-post_install')
class TestInfobipExten(InfobipTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.connect_user = cls._create_connect_user('ib_extenuser1')
        cls.exten = cls.env['connect.infobip.exten'].create({
            'number': '8200',
            'model': 'connect.user',
            'res_id': cls.connect_user.id,
        })

    def test_create_exten(self):
        self.assertTrue(self.exten.id)
        self.assertEqual(self.exten.number, '8200')

    def test_unique_number(self):
        with self.assertRaises(Exception):
            self.env['connect.infobip.exten'].create({
                'number': '8200',
                'model': 'connect.user',
                'res_id': self.connect_user.id,
            })

    def test_model_friendly_compute(self):
        self.assertEqual(self.exten.model_friendly, 'User')

    def test_dst_compute(self):
        self.assertEqual(self.exten.dst._name, 'connect.user')
        self.assertEqual(self.exten.dst.id, self.connect_user.id)

    def test_user_back_link(self):
        self.assertEqual(self.connect_user.infobip_exten, self.exten)
        self.assertEqual(self.connect_user.infobip_exten_number, '8200')

    def test_pbx_number_fields(self):
        self.assertIn(
            'infobip_exten_number',
            self.env['connect.user']._pbx_number_fields())

    def test_unlink_clears_dst_exten(self):
        self.exten.unlink()
        self.assertFalse(self.connect_user.infobip_exten)

    def test_create_reuses_orphan_exten(self):
        orphan = self.env['connect.infobip.exten'].create({'number': '500'})
        new_exten = self.env['connect.infobip.exten'].create({
            'number': '500',
            'model': 'connect.user',
            'res_id': self.connect_user.id,
        })
        self.assertEqual(orphan.id, new_exten.id)

    def test_create_extension_action(self):
        result = self.env['connect.infobip.exten'].create_extension(
            self.connect_user, 'connect.user',
            current_exten=self.connect_user.infobip_exten)
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'connect.infobip.exten')
