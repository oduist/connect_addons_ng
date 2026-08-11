from contextlib import contextmanager
from unittest.mock import patch

from odoo import Command, fields
from odoo.tests.common import TransactionCase


class ConnectAccountTestCommon(TransactionCase):
    # Deliberately NOT based on AccountTestInvoicingCommon: that scaffold
    # builds a whole demo company including products, and product creation
    # breaks whenever a module loaded later in the graph has added a required
    # column to product.template (website_sale's base_unit_count). These tests
    # never touch products — they post invoices with explicit account_id — so
    # the minimal company/user setup below is both sufficient and immune to
    # co-installation order.

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Run as a user holding accounting rights (to post invoices), contact
        # creation (the test partner) and Connect Admin (to create
        # connect.call / connect.channel while driving process_call_event()).
        cls.test_user = cls.env['res.users'].create({
            'name': 'Connect Account Tester',
            'login': 'connect_account_tester',
            'group_ids': [Command.set([
                cls.env.ref('base.group_user').id,
                cls.env.ref('base.group_partner_manager').id,
                cls.env.ref('account.group_account_manager').id,
                cls.env.ref('connect.group_admin').id,
            ])],
        })
        cls.env = cls.env(user=cls.test_user)
        cls.Move = cls.env['account.move']
        cls.Call = cls.env['connect.call']
        cls.Settings = cls.env['connect.settings'].sudo()
        cls.webhook_user = cls.env.ref('connect.user_connect_webhook')
        # The test company has no chart of accounts pre-configured, so
        # collect_company_accounting_data() (run by AccountTestInvoicingCommon)
        # finds no existing accounts/journals either; create the minimal set
        # invoice posting requires.
        cls.revenue_account = cls._get_or_create_account('income', 'Test Revenue')
        cls.expense_account = cls._get_or_create_account('expense', 'Test Expense')
        cls.receivable_account = cls._get_or_create_account('asset_receivable', 'Test Receivable')
        cls.payable_account = cls._get_or_create_account('liability_payable', 'Test Payable')
        cls.transfer_account = cls._get_or_create_account('asset_current', 'Test Transfer Account')
        if not cls.env.company.transfer_account_id:
            cls.env.company.transfer_account_id = cls.transfer_account
        cls.sale_journal = cls._get_or_create_journal('sale', 'Test Customer Invoices')
        cls.purchase_journal = cls._get_or_create_journal('purchase', 'Test Vendor Bills')
        cls.partner = cls._create_partner()

    # Deterministic test-only account codes, one per account type used below.
    _TEST_ACCOUNT_CODES = {
        'income': 'TST4000',
        'expense': 'TST6000',
        'asset_receivable': 'TST1200',
        'liability_payable': 'TST4400',
        'asset_current': 'TST1010',
    }

    @classmethod
    def _get_or_create_account(cls, account_type, name):
        account = cls.env['account.account'].search([
            ('account_type', '=', account_type),
            ('company_ids', 'in', cls.env.company.id),
        ], limit=1)
        if not account:
            account = cls.env['account.account'].create({
                'name': name,
                'code': cls._TEST_ACCOUNT_CODES[account_type],
                'account_type': account_type,
                'company_ids': [Command.set([cls.env.company.id])],
            })
        return account

    @classmethod
    def _get_or_create_journal(cls, journal_type, name):
        journal = cls.env['account.journal'].search([
            ('type', '=', journal_type),
            ('company_id', '=', cls.env.company.id),
        ], limit=1)
        if not journal:
            journal = cls.env['account.journal'].create({
                'name': name,
                'code': 'TST{}'.format(journal_type[:3].upper()),
                'type': journal_type,
                'company_id': cls.env.company.id,
            })
        return journal

    @classmethod
    def _create_partner(cls, **vals):
        defaults = {
            'name': 'Acme Ltd',
            'phone': '+380671111111',
            'property_account_receivable_id': cls.receivable_account.id,
            'property_account_payable_id': cls.payable_account.id,
        }
        defaults.update(vals)
        return cls.env['res.partner'].with_context(no_clear_cache=True).create(defaults)

    @classmethod
    def _post_invoice(cls, move_type='out_invoice', partner=None, pay=False, **vals):
        partner = partner or cls.partner
        account = cls.revenue_account if move_type == 'out_invoice' else cls.expense_account
        journal = cls.sale_journal if move_type == 'out_invoice' else cls.purchase_journal
        defaults = {
            'move_type': move_type,
            'partner_id': partner.id,
            'journal_id': journal.id,
            'invoice_date': fields.Date.context_today(cls.env.user),
            'invoice_line_ids': [Command.create({
                'name': 'Test line',
                'quantity': 1,
                'price_unit': 100.0,
                'account_id': account.id,
            })],
        }
        defaults.update(vals)
        move = cls.Move.create(defaults)
        move.action_post()
        if pay:
            cls.env['account.payment.register'].with_context(
                active_model='account.move', active_ids=move.ids,
            ).create({}).action_create_payments()
        return move

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
