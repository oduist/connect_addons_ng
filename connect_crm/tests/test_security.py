from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import ConnectCrmTestCommon


@tagged('post_install', '-at_install', 'connect_crm_security')
class TestWebhookAccess(ConnectCrmTestCommon):

    def test_webhook_user_exists(self):
        self.assertTrue(self.webhook_user)
        self.assertTrue(self.webhook_user.has_group('connect.group_webhook'))

    def test_webhook_user_can_create_lead(self):
        lead = self.Lead.with_user(self.webhook_user).create(
            {'name': 'WebhookLead', 'phone': '+380672727277'})
        self.assertTrue(lead.id)

    def test_webhook_user_can_write_lead(self):
        lead = self.Lead.create({'name': 'ByAdmin', 'phone': '+380672828288'})
        lead.with_user(self.webhook_user).write({'description': 'updated'})
        lead.invalidate_recordset(['description'])
        self.assertIn('updated', lead.description or '')

    def test_webhook_user_cannot_unlink_lead(self):
        lead = self.Lead.create({'name': 'Protected', 'phone': '+380672929299'})
        with mute_logger('odoo.addons.base.models.ir_model'), self.assertRaises(AccessError):
            lead.with_user(self.webhook_user).unlink()

    def test_webhook_user_can_read_crm_stage(self):
        stages = self.env['crm.stage'].with_user(self.webhook_user).search([], limit=1)
        # Only assert no AccessError is raised; stages may or may not exist in some configs.
        self.assertIsNotNone(stages.ids)

    def test_webhook_user_can_read_crm_team(self):
        teams = self.env['crm.team'].with_user(self.webhook_user).search([], limit=1)
        self.assertIsNotNone(teams.ids)

    def test_webhook_user_can_read_mail_alias_domain(self):
        domains = self.env['mail.alias.domain'].with_user(self.webhook_user).search([], limit=1)
        self.assertIsNotNone(domains.ids)
