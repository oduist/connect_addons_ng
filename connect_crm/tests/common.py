from contextlib import contextmanager
from unittest.mock import patch

from odoo.tests import TransactionCase, new_test_user


class ConnectCrmTestCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Lead = cls.env['crm.lead']
        cls.Call = cls.env['connect.call']
        cls.Source = cls.env['utm.source']
        cls.Settings = cls.env['connect.settings'].sudo()

        cls.admin_user = new_test_user(
            cls.env, login='crm_admin',
            groups='base.group_user,base.group_system,base.group_erp_manager,sales_team.group_sale_manager',
        )
        cls.salesperson = new_test_user(
            cls.env, login='crm_seller',
            groups='base.group_user,sales_team.group_sale_salesman',
        )
        cls.webhook_user = cls.env.ref('connect.user_connect_webhook')

        cls.partner = cls.env['res.partner'].with_context(no_clear_cache=True).create({
            'name': 'Acme Ltd',
            'phone': '+380671010101',
        })

    @classmethod
    def _create_lead(cls, **vals):
        defaults = {'name': 'Test Lead', 'type': 'lead'}
        defaults.update(vals)
        return cls.Lead.create(defaults)

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

    def _set_autocreate_flags(self, **flags):
        """Apply auto-create settings and default salesperson."""
        defaults = {
            'auto_create_leads_for_in_calls': False,
            'auto_create_leads_for_in_answered_calls': True,
            'auto_create_leads_for_in_missed_calls': True,
            'auto_create_leads_for_in_unknown_callers': True,
            'auto_create_leads_for_out_calls': False,
            'auto_create_leads_for_out_answered_calls': True,
            'auto_create_leads_for_out_missed_calls': True,
            'auto_create_leads_type': 'lead',
        }
        defaults.update(flags)
        for key, value in defaults.items():
            self.Settings.set_param(key, value)
        self.Settings.set_param('auto_create_leads_sales_person', self.salesperson.id)
        self.env.flush_all()

    @contextmanager
    def mock_license_check(self, result=True):
        with patch.object(
            type(self.env['oduist.license']),
            'check_license',
            return_value=result,
        ):
            yield

    @contextmanager
    def mock_reload_view(self):
        with patch.object(
            type(self.env['connect.settings']),
            'connect_reload_view',
        ):
            yield
