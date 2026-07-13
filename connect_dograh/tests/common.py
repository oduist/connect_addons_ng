# -*- coding: utf-8 -*-
from unittest.mock import MagicMock

from odoo.tests import TransactionCase

TEST_TOKEN = 'test-dograh-service-token-12345678'


def make_response(status_code=200, json_data=None):
    """Build a requests.Response-like mock for Dograh HTTP calls."""
    response = MagicMock()
    response.status_code = status_code
    if json_data is None:
        json_data = {}
    response.json.return_value = json_data
    response.text = str(json_data)
    return response


class DograhTestCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.settings = cls.env['connect.settings'].sudo()
        cls.settings.set_param('dograh_api_url', 'https://dograh.example.com')
        cls.settings.set_param('dograh_account_id', 'odoo-test')
        cls.settings.set_param('dograh_service_token', TEST_TOKEN)

    @classmethod
    def _create_agent(cls, **kwargs):
        vals = {'name': 'Test Agent'}
        vals.update(kwargs)
        return cls.env['connect.dograh.agent'].create(vals)

    @classmethod
    def _create_extension(cls, agent, number='9001'):
        return cls.env['connect.freeswitch.exten'].create({
            'number': number,
            'dst': 'connect.dograh.agent,{}'.format(agent.id),
        })
