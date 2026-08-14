# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import TwilioTestCommon


@tagged('at_install', '-post_install')
class TestWhatsAppSender(TwilioTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sender_model = cls.env['connect.whatsapp_sender']
        cls.offline_sender = cls.sender_model.create({
            'number': '+15550001001',
            'status': 'OFFLINE',
            'is_default': True,
        })
        cls.online_sender = cls.sender_model.create({
            'number': '+15550001002',
            'status': 'ONLINE',
        })
        cls.connect_user = cls._create_connect_user('tw_whatsapp_sender')

    def test_offline_default_is_skipped(self):
        sender = self.sender_model.get_default_sender(self.connect_user)

        self.assertEqual(sender, self.online_sender)

    def test_offline_user_preference_is_skipped(self):
        self.connect_user.whatsapp_sender_id = self.offline_sender

        sender = self.sender_model.get_default_sender(self.connect_user)

        self.assertEqual(sender, self.online_sender)

    def test_online_user_preference_is_used(self):
        self.connect_user.whatsapp_sender_id = self.online_sender

        sender = self.sender_model.get_default_sender(self.connect_user)

        self.assertEqual(sender, self.online_sender)

    def test_no_sender_when_all_are_offline(self):
        self.online_sender.status = 'OFFLINE'

        sender = self.sender_model.get_default_sender(self.connect_user)

        self.assertFalse(sender)

    def test_user_sender_field_only_offers_online_synced_records(self):
        domain = self.env['connect.user']._fields['whatsapp_sender_id'].domain

        self.assertIn(('no_sync', '=', False), domain)
        self.assertIn(('status', '=', 'ONLINE'), domain)
