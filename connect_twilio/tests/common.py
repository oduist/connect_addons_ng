# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, new_test_user


class TwilioTestCommon(TransactionCase):

    @classmethod
    def _create_connect_user(cls, login, **kwargs):
        odoo_user = new_test_user(cls.env, login=login)
        vals = {'user': odoo_user.id}
        vals.update(kwargs)
        return cls.env['connect.user'].with_context(
            no_clear_cache=True, no_twilio_create=True).create(vals)
