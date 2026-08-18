# -*- coding: utf-8 -*-
from odoo import release
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
        # api_url is a non-stored compute: a set_param only lands in the
        # compute cache, so write the backing config parameter instead to
        # survive cache invalidation within a test.
        cls.env['ir.config_parameter'].sudo().set_param(
            'connect.api_url', 'https://odoo.example.test/')
        cls.domain = cls.env['connect.telnyx.domain'].with_context(
            no_telnyx_create=True).create({
                'friendly_name': 'Test Domain',
                'subdomain': 'test-connect',
                'sid': 'connection-test',
            })

    @classmethod
    def _create_connect_user(cls, login, **kwargs):
        odoo_user = new_test_user(cls.env, login=login)
        vals = {'user': odoo_user.id}
        vals.update(kwargs)
        return cls.env['connect.user'].with_context(
            no_clear_cache=True, no_telnyx_create=True).create(vals)

    @classmethod
    def _grant_group(cls, user, xmlid):
        # res.users.groups_id was renamed to group_ids in Odoo 19.
        field = 'group_ids' if release.version_info[0] >= 19 else 'groups_id'
        user.write({field: [(4, cls.env.ref(xmlid).id)]})

    @classmethod
    def _create_web_phone_user(cls, login, **kwargs):
        """A PBX user whose web phone is ready to be dialled."""
        vals = {
            'telnyx_domain': cls.domain.id,
            'telnyx_client_enabled': True,
            'telnyx_client_username': 'client-{}'.format(login),
        }
        vals.update(kwargs)
        return cls._create_connect_user(login, **vals)
