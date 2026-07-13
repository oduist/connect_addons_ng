# -*- coding: utf-8 -*-
"""Access matrix of the connect.infobip.* models (mirrors Twilio/Telnyx,
ADR-036)."""
from odoo.exceptions import AccessError
from odoo.tests import tagged, new_test_user

from .common import InfobipTestCommon


@tagged('at_install', '-post_install')
class TestInfobipAcl(InfobipTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.plain_user = new_test_user(
            cls.env, login='ib_acl_user', groups='connect.group_user')
        cls.number = cls.env['connect.infobip.number'].with_context(
            skip_infobip_sync=True).create({
                'phone_number': '+15550001111',
                'number_key': 'NK1',
            })
        cls.callerid = cls.env['connect.infobip.outgoing_callerid'].create({
            'number': '+15550001111',
            'friendly_name': 'Main',
        })
        cls.sender = cls.env['connect.infobip.whatsapp_sender'].create({
            'number': '+15550001111',
            'status': 'ACTIVE',
        })

    def test_user_reads_config_models(self):
        for model in ['connect.infobip.number', 'connect.infobip.exten',
                      'connect.infobip.outgoing_callerid',
                      'connect.infobip.whatsapp_sender',
                      'connect.infobip.whatsapp_template',
                      'connect.infobip.user_callflow']:
            self.env[model].with_user(self.plain_user).search([])

    def test_user_cannot_write_number(self):
        with self.assertRaises(AccessError):
            self.number.with_user(self.plain_user).write(
                {'friendly_name': 'nope'})

    def test_user_cannot_create_callerid(self):
        with self.assertRaises(AccessError):
            self.env['connect.infobip.outgoing_callerid'].with_user(
                self.plain_user).create({
                    'number': '+15550009999',
                    'friendly_name': 'nope',
                })

    def test_user_no_access_message_configuration(self):
        with self.assertRaises(AccessError):
            self.env['connect.infobip.message_configuration'].with_user(
                self.plain_user).search([])

    def test_user_creates_whatsapp_composer(self):
        composer = self.env['connect.infobip.whatsapp_composer'].with_user(
            self.plain_user).create({
                'whatsapp_sender_id': self.sender.id,
                'phone': '+15550002222',
                'body': 'hello',
            })
        self.assertTrue(composer.id)
