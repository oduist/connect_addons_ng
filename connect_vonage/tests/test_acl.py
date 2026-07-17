# -*- coding: utf-8 -*-
"""ACL tests for the connect.ncco model (ADR-036)."""
import json

from odoo.exceptions import AccessError
from odoo.tests import tagged, new_test_user

from .common import VonageTestCommon


@tagged('at_install', '-post_install')
class TestVonageAcl(VonageTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ncco = cls.env['connect.ncco'].create({
            'name': 'ACL probe',
            'ncco': json.dumps([{'action': 'talk', 'text': 'Hi'}]),
        })
        cls.connect_user = new_test_user(
            cls.env, login='vonage_acl_user',
            groups='base.group_user,connect.group_user')
        cls.plain_user = new_test_user(
            cls.env, login='vonage_acl_plain', groups='base.group_user')

    def test_connect_user_can_read(self):
        record = self.env['connect.ncco'].with_user(
            self.connect_user).browse(self.ncco.id)
        self.assertEqual(record.name, 'ACL probe')

    def test_connect_user_cannot_write(self):
        with self.assertRaises(AccessError):
            self.env['connect.ncco'].with_user(
                self.connect_user).browse(self.ncco.id).write(
                    {'name': 'Hacked'})

    def test_connect_user_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['connect.ncco'].with_user(self.connect_user).create(
                {'name': 'New', 'ncco': '[]'})

    def test_plain_user_cannot_read(self):
        with self.assertRaises(AccessError):
            self.env['connect.ncco'].with_user(
                self.plain_user).browse(self.ncco.id).read(['name'])

    def test_webhook_user_can_read(self):
        webhook_user = self.env.ref('connect.user_connect_webhook')
        record = self.env['connect.ncco'].with_user(
            webhook_user).browse(self.ncco.id)
        self.assertEqual(record.name, 'ACL probe')
