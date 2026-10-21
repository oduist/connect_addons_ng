# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, new_test_user


class VoiceTelTestCommon(TransactionCase):

    @classmethod
    def _create_connect_user(cls, login, **kwargs):
        odoo_user = new_test_user(cls.env, login=login)
        vals = {
            'user': odoo_user.id,
            'voicetel_sip_enabled': False,
        }
        vals.update(kwargs)
        return cls.env['connect.user'].with_context(
            no_clear_cache=True, no_voicetel_create=True).create(vals)
