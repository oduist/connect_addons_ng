# -*- coding: utf-8 -*-
"""Shared fixtures for connect_3cx tests."""
from odoo.tests import TransactionCase, new_test_user

API_KEY = 'test-3cx-api-key-0123456789abcdef'
PBX_URL = 'https://pbx.example.com'
ODOO_URL = 'https://odoo.example.com'


def setup_threecx_settings(env):
    """Configure the 3CX integration on the settings singleton."""
    Settings = env['connect.settings']
    Settings.set_param('threecx_enabled', True)
    Settings.set_param('threecx_api_key', API_KEY)
    Settings.set_param('threecx_pbx_url', PBX_URL)
    env['ir.config_parameter'].sudo().set_param('connect.api_url', ODOO_URL)


class ThreeCXTestCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Settings = cls.env['connect.settings']
        cls.Channel = cls.env['connect.channel']
        cls.Call = cls.env['connect.call']
        setup_threecx_settings(cls.env)
        cls.odoo_user = new_test_user(
            cls.env, login='tcx_user_101', groups='base.group_user')
        cls.connect_user = cls.env['connect.user'].with_context(
            no_clear_cache=True).create({
                'user': cls.odoo_user.id,
                'threecx_exten': '101',
                'originate_provider': '3cx',
            })
        cls.partner = cls.env['res.partner'].with_context(
            no_clear_cache=True).create({
                'name': '3CX Test Partner',
                'phone': '+15551234567',
            })
