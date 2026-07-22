from contextlib import contextmanager
from unittest.mock import patch

from odoo.tests import TransactionCase


class ConnectHrTestCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Employee = cls.env['hr.employee']
        cls.Call = cls.env['connect.call']
        cls.Settings = cls.env['connect.settings'].sudo()
        cls.webhook_user = cls.env.ref('connect.user_connect_webhook')

    @classmethod
    def _create_call(cls, **vals):
        defaults = {
            'caller': '+380671111111',
            'called': '+380670000001',
            'direction': 'incoming',
            'status': 'completed',
        }
        defaults.update(vals)
        return cls.Call.sudo().with_context(tracking_disable=True).create(defaults)

    @contextmanager
    def mock_license_check(self, result=True):
        with patch.object(
            type(self.env['oduist.license']),
            'check_license',
            return_value=result,
        ):
            yield
