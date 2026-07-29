from contextlib import contextmanager
from unittest.mock import patch

from odoo.tests import TransactionCase


class ConnectProjectTestCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Task = cls.env['project.task']
        cls.Project = cls.env['project.project']
        cls.Call = cls.env['connect.call']
        cls.Settings = cls.env['connect.settings'].sudo()
        cls.webhook_user = cls.env.ref('connect.user_connect_webhook')
        cls.partner = cls._create_partner()

    @classmethod
    def _create_partner(cls, **vals):
        defaults = {
            'name': 'Acme Ltd',
            'phone': '+380671111111',
        }
        defaults.update(vals)
        return cls.env['res.partner'].with_context(no_clear_cache=True).create(defaults)

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

    @classmethod
    def _create_channel(cls, sid, caller='+380671111111', called='+380670000001', **kwargs):
        # Mirrors connect/tests/common.py's _create_channel — needed to
        # drive the real connect.call.process_call_event() hook end-to-end
        # (first-leg channel -> call creation) instead of faking the call.
        vals = {
            'sid': sid,
            'caller': caller,
            'called': called,
            'status': 'ringing',
            'technical_direction': 'inbound',
            'call_type': 'phone',
        }
        vals.update(kwargs)
        return cls.env['connect.channel'].with_context(tracking_disable=True).create(vals)

    @contextmanager
    def mock_license_check(self, result=True):
        with patch.object(
            type(self.env['oduist.license']),
            'check_license',
            return_value=result,
        ):
            yield

    @contextmanager
    def mock_connect_reload_view(self):
        with patch.object(
            type(self.env['connect.settings']),
            'connect_reload_view',
        ):
            yield
