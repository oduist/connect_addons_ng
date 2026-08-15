# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, new_test_user


class TelnyxTestCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        settings = cls.env['connect.settings'].sudo()
        # A key must be present for get_telnyx_client() to build a client;
        # no test is allowed to reach the network, so its value is fake.
        settings.set_param('telnyx_api_key', 'test-api-key')
        settings.set_param('telnyx_auto_sync', False)
        settings.set_param('api_url', 'https://odoo.example.test/')

    @classmethod
    def _create_connect_user(cls, login, **kwargs):
        odoo_user = new_test_user(cls.env, login=login)
        vals = {'user': odoo_user.id}
        vals.update(kwargs)
        return cls.env['connect.user'].with_context(
            no_clear_cache=True, no_telnyx_create=True).create(vals)
