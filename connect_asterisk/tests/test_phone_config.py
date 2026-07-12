# -*- coding: utf-8 -*-
"""Web phone configuration (get_sip_user_config) tests."""
from odoo.tests import tagged, new_test_user

from .common import AsteriskTestCommon


@tagged('post_install', '-at_install', 'connect_asterisk')
class TestPhoneConfig(AsteriskTestCommon):

    def test_no_webrtc_endpoint_returns_false(self):
        # The default endpoint is UDP — no web phone config.
        result = self.env['res.users'].with_user(
            self.odoo_user).get_sip_user_config(self.odoo_user.id)
        self.assertFalse(result)

    def test_webrtc_endpoint_config(self):
        self.endpoint.sudo().asterisk_sip_transport = 'webrtc'
        result = self.env['res.users'].with_user(
            self.odoo_user).get_sip_user_config(self.odoo_user.id)
        self.assertTrue(result)
        self.assertEqual(result['user_config']['sip_user'], '101')
        self.assertEqual(
            result['user_config']['sip_password'],
            self.endpoint.sudo().asterisk_sip_password)
        self.assertIn('phone_ring_volume', result['phone_config'])
        self.assertIn('mask_call_number', result['phone_config'])

    def test_other_user_config_denied(self):
        self.endpoint.sudo().asterisk_sip_transport = 'webrtc'
        other = new_test_user(
            self.env, login='ast_other', groups='base.group_user')
        result = self.env['res.users'].with_user(
            other).get_sip_user_config(self.odoo_user.id)
        self.assertFalse(result)

    def test_search_pbx_users_requires_group(self):
        self.connect_user.create_extension()
        found = self.env['connect.user'].with_user(
            self.odoo_user).search_pbx_users(self.odoo_user.name)
        self.assertTrue(found)
        self.assertEqual(found[0]['name'], self.connect_user.name)
