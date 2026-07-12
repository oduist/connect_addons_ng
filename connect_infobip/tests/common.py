# -*- coding: utf-8 -*-
from unittest.mock import MagicMock

from odoo.tests import TransactionCase, new_test_user


def make_response(status_code=200, json_data=None, content=b'{}'):
    """Build a requests.Response-like mock for infobip_api_request tests."""
    response = MagicMock()
    response.status_code = status_code
    response.content = content
    if json_data is None:
        json_data = {}
    response.json.return_value = json_data
    return response


class InfobipTestCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.settings = cls.env['connect.settings'].sudo()
        # Seed the singleton: fake credentials, verification off so tests
        # never hit the network or the webhook auth path.
        cls.settings.set_param('infobip_base_url', 'https://test.api.infobip.com')
        cls.settings.set_param('infobip_api_key', 'TESTKEY123')
        cls.settings.set_param('infobip_verify_requests', False)
        cls.settings.set_param('infobip_auto_sync', False)
        cls.settings.set_param('infobip_calls_configuration_id', 'cfg-test')

    @classmethod
    def _create_connect_user(cls, login, **kwargs):
        odoo_user = new_test_user(cls.env, login=login)
        vals = {'user': odoo_user.id}
        vals.update(kwargs)
        return cls.env['connect.user'].with_context(
            no_clear_cache=True, no_infobip_create=True).create(vals)
