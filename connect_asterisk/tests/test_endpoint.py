# -*- coding: utf-8 -*-
"""connect.asterisk.endpoint tests."""
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import AsteriskTestCommon


@tagged('post_install', '-at_install', 'connect_asterisk')
class TestAsteriskEndpoint(AsteriskTestCommon):

    def test_sip_user_computed_from_channel(self):
        self.assertEqual(self.endpoint.asterisk_sip_user, '101')

    def test_sip_password_generated_on_create(self):
        self.assertTrue(self.endpoint.sudo().asterisk_sip_password)

    def test_regenerate_password(self):
        old = self.endpoint.sudo().asterisk_sip_password
        self.endpoint.sudo().action_regenerate_asterisk_sip_password()
        self.assertNotEqual(self.endpoint.sudo().asterisk_sip_password, old)

    def test_channel_format_constraint(self):
        with self.assertRaises(ValidationError):
            self.env['connect.asterisk.endpoint'].create({
                'name': 'Bad', 'asterisk_channel': 'PJSIP101'})
        with self.assertRaises(ValidationError):
            self.env['connect.asterisk.endpoint'].create({
                'name': 'Bad', 'asterisk_channel': 'PJSIP/1 01'})

    def test_channel_unique_constraint(self):
        with self.assertRaises(ValidationError):
            self.env['connect.asterisk.endpoint'].create({
                'name': 'Duplicate', 'asterisk_channel': 'PJSIP/101'})

    def test_get_endpoint_by_channel(self):
        Endpoint = self.env['connect.asterisk.endpoint']
        self.assertEqual(
            Endpoint.get_endpoint_by_channel('PJSIP/101-0000af'),
            self.endpoint)
        self.assertEqual(
            Endpoint.get_endpoint_by_channel('PJSIP/101'), self.endpoint)
        self.assertFalse(Endpoint.get_endpoint_by_channel('PJSIP/999-0001'))
        self.assertFalse(Endpoint.get_endpoint_by_channel(''))

    def test_get_user_by_uri(self):
        User = self.env['connect.user']
        self.assertEqual(
            User.get_user_by_uri('sip:101@pbx.example.com'),
            self.connect_user)
        self.assertEqual(User.get_user_by_uri('101'), self.connect_user)
        self.assertFalse(User.get_user_by_uri('sip:999@pbx.example.com'))
        self.assertFalse(User.get_user_by_uri(False))

    def test_originate_variables(self):
        self.endpoint.asterisk_auto_answer_header = 'Answer-Mode: Auto'
        self.connect_user.asterisk_originate_vars = 'FOO=bar\n\nBAZ=1'
        variables = self.endpoint._get_originate_variables()
        self.assertIn('PJSIP_HEADER(add,Answer-Mode)=Auto', variables)
        self.assertIn('FOO=bar', variables)
        self.assertIn('BAZ=1', variables)

    def test_originate_variables_sip_header(self):
        endpoint = self.env['connect.asterisk.endpoint'].create({
            'name': 'Old phone', 'asterisk_channel': 'SIP/103',
            'asterisk_auto_answer_header': 'Answer-Mode: Auto',
        })
        variables = endpoint._get_originate_variables()
        self.assertIn('SIPADDHEADER=Answer-Mode: Auto', variables)
