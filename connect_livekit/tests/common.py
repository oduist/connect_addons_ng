from contextlib import contextmanager
from unittest.mock import patch, MagicMock

from odoo.tests import TransactionCase, new_test_user


class LivekitTestCommon(TransactionCase):
    """Base case for connect_livekit tests.

    livekit_api_call() is mocked by default so no LiveKit server is
    needed; tests that assert on the outgoing request inspect the
    recorded (path, request) calls.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin_user = new_test_user(
            cls.env, login='lk_admin',
            groups='base.group_user,base.group_system,'
                   'base.group_erp_manager,connect.group_admin')
        # new_test_user does not create the PBX user; several models need it.
        cls.connect_user = cls.env['connect.user'].with_context(
            no_clear_cache=True).create({'user': cls.admin_user.id})
        cls.settings = cls.env['connect.settings']
        cls.settings.sudo().set_param('livekit_ws_url', 'ws://livekit:7880')
        cls.settings.sudo().set_param('livekit_api_key', 'APIkey')
        cls.settings.sudo().set_param('livekit_api_secret', 'secret-value')
        cls.settings.sudo().set_param('api_url', 'https://odoo.example.com')
        cls.settings.sudo().set_param('livekit_auto_sync', False)
        cls.partner = cls.env['res.partner'].with_context(
            no_clear_cache=True).create({
                'name': 'LK Partner',
                'phone': '+15551230000',
            })

    @contextmanager
    def mock_api(self, return_value=None, side_effect=None):
        """Patch connect.settings.livekit_api_call and yield the mock."""
        mock = MagicMock(name='livekit_api_call')
        if side_effect is not None:
            mock.side_effect = side_effect
        elif return_value is not None:
            mock.return_value = return_value
        else:
            mock.return_value = MagicMock()
        with patch.object(
            type(self.env['connect.settings']),
            'livekit_api_call', mock,
        ):
            yield mock

    @contextmanager
    def mock_license_check(self, result=True):
        with patch.object(
            type(self.env['oduist.license']),
            'check_license', return_value=result,
        ):
            yield

    def _create_agent(self, **kwargs):
        vals = {
            'name': 'Test Agent',
            'instructions': 'Be helpful.',
        }
        vals.update(kwargs)
        return self.env['connect.livekit.agent'].create(vals)

    def _create_trunk(self, **kwargs):
        vals = {
            'name': 'Test Trunk',
            'outbound_address': 'sip.carrier.example.com',
        }
        vals.update(kwargs)
        return self.env['connect.livekit.trunk'].create(vals)
